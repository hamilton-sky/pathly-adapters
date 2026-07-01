# Happy Flow — unified-cli-composition (Gate 2)

_The end-to-end user experience when everything works correctly._

---

## Flow 1 — Summary action fails and renders an error pill (US-01)

1. User runs a Summary action on an artifact in Studio.
2. The CLI engine processes the artifact and writes `ERROR: source file is binary; cannot summarize` to the output file.
3. The renderer's polling hook in `useEditorAgentActions.ts` reads the output file, detects the `ERROR:` prefix.
4. The Summary ActionPill transitions to `state='error'`. The error text "source file is binary; cannot summarize" is visible inside the pill.
5. No toast is shown (or a toast supplements — but the pill is the primary feedback). The user can clearly see which action failed.

---

## Flow 2 — Standalone Analyze (no goal_id) — fragments not injected

1. User runs Analyze on a file in the markdown editor.
2. Studio calls `POST /skills/compose` with `skill: "editor/analyze"` and no `goal_id` in the context.
3. `compose.py` builds adapter_caps via `build_adapter_caps(ctx)`. `goal_id` is `None`.
4. `board-start-context` requires `goal_id` — skipped. `task-dag-post` requires `goal_id` — skipped.
5. Composed prompt = skill body + `client-file-output` + `artifact-transform` (the standalone-transform profile).
6. Agent runs, writes `.analysis` output file. Renderer polls and displays the result. No board interaction.

---

## Flow 3 — Goal Decompose with board context (US-02, US-03, US-05, US-06, US-07, US-08)

1. User triggers goal Decompose for "feature X" (goal_id = `g-123`).
2. Supervisor calls `compose_skill("planning/plan", build_adapter_caps({"goal_id": "g-123", "executor": "single", "kind": "agent"}), manifest)`.
3. `compose.py` reads the `planning/plan` manifest entry. `goal_id` is present → includes `board-start-context` and `task-dag-post`.
4. Composed prompt = planning/plan skill body + `board-start-context` + `task-dag-post` + `comms-post` + `progress-logging`.
5. Supervisor logs `PHASE_START` event with `{goal_id: "g-123", executor: "single", kind: "agent"}`.
6. Supervisor spawns the CLI engine headlessly with the composed prompt as argv. `_dash_safe_prompt` verifies no leading `---`.
7. Agent starts. Reads `board-start-context` instruction → calls `GET /comms/retrieve?scope=feature-x&goal_id=g-123&limit=10`.
8. Board returns governance lines, active tasks, recent decisions. Agent treats this as read-only preamble.
9. Agent reasons about the goal, produces a task tree.
10. Agent calls `POST /comms/post` with `type: "task"` for each task in the tree, using the payload template from `task-dag-post`.
11. Agent writes `AGENT_DONE` to EVENTS.jsonl with `summary` field containing the posted task IDs and a brief decomposition narrative.
12. CLI engine exits.
13. Supervisor reads `AGENT_DONE.summary` from EVENTS.jsonl (no stdout parsing). Records the task IDs.
14. The board now shows a populated task DAG for goal `g-123`, equivalent in structure to what the old hard-coded path produced.

---

## Flow 4 — Developer adds a new fragment to Decompose (US-10)

1. Developer wants to inject a `context-limit-contract` fragment into every Decompose run.
2. Developer opens `src/pathly_data/core/skills/composition.yaml`, finds the `planning/plan` entry.
3. Adds `{ name: context-limit-contract }` (no `requires:` — always included).
4. No Python changes needed.
5. Next Decompose run automatically includes the new fragment in the composed prompt.
6. Developer decides the fragment is not needed. Removes it from the manifest. Next run is clean again.
7. Zero code changes required — only the manifest edit.

---

## Flow 5 — Both paths compose identically for same context (US-09)

1. A renderer-driven `POST /skills/compose` call arrives at `editor_render.py` with `goal_id: "g-456"`.
2. `editor_render.py` calls `build_adapter_caps(ctx)` → `{"can_spawn": True, "goal_id": "g-456", "executor": "single", "kind": "agent"}`.
3. An in-process supervisor call in `goal_decomposer.py` for the same goal calls `build_adapter_caps(ctx)` with the same context values.
4. Both paths pass identical adapter_caps to `compose_skill()`.
5. Both paths receive the same composed prompt.
6. A developer adds a new field to `build_adapter_caps()`. Both paths pick it up automatically. No call-site code change.
