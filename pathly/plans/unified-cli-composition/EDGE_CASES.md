# Edge Cases — unified-cli-composition (Gate 2)

_Focus: migration risk, fragment gating boundaries, result-capture contract, and error surfaces._

---

## EC-01 — `goal_id` absent at compose time (standalone transform)

**Risk:** `board-start-context` and `task-dag-post` fragments appear in a composed prompt even when called without a `goal_id` (e.g., a standalone Analyze or Split action).

**Expected behavior:** Both fragments are silently skipped. The composed prompt contains neither. No error is raised, no empty section header appears.

**Boundary test:** `compose_skill("planning/plan", {"can_spawn": True, "goal_id": None}, manifest)` must return only the skill body + any default fragments. Grep the result for "board-start-context" and "GET /comms/retrieve" — neither should appear.

---

## EC-02 — Board unreachable when agent runs `board-start-context`

**Risk:** Agent call to `GET /comms/retrieve` fails (connection refused, 500, timeout). Agent aborts the run or enters a retry loop.

**Expected behavior:** The `board-start-context` fragment's skip-if-down advisory guard fires. Agent emits "board context unavailable" inline and continues with the task body only. The Decompose result (task DAG) is still posted.

**Edge:** The fragment must not instruct the agent to raise an error or halt. The guard must use "if the board is unreachable, skip this section and continue" language.

---

## EC-03 — Board unreachable when agent runs `task-dag-post`

**Risk:** Agent call to `POST /comms/post` with `type: "task"` fails. Agent retries indefinitely or silently drops the tasks.

**Expected behavior:** The fragment's skip-if-down advisory fires. Agent notes that the board write failed, writes a warning into its `AGENT_DONE.summary`, and exits. The supervisor reads the summary and surfaces the warning. Tasks are not partially posted (partial DAGs must be considered an error state, not a success).

**Edge:** A partial task DAG (some tasks posted, board goes down mid-write) is worse than no DAG. The fragment should instruct the agent to post all-or-nothing if feasible, or to list un-posted tasks in the summary so the operator can retry.

---

## EC-04 — Decompose runs while board-start-context is already being fetched (re-entrant goal)

**Risk:** Two Decompose runs for the same goal start near-simultaneously. Both fetch board context; both post task trees. The board ends up with duplicate tasks.

**Expected behavior:** This is a supervisor-level guard (not a fragment concern). The fragment itself is stateless. The supervisor's existing concurrency controls (one active run per goal) must remain in place. The fragment should not add idempotency logic — that belongs in the supervisor.

**Note for builder:** Do not add deduplication logic to the fragment. Verify the supervisor's existing per-goal lock is not removed during conversion.

---

## EC-05 — `_decompose_planner()` path receives a manifest entry that does not exist

**Risk:** `compose_skill("planning/plan", ...)` is called before the manifest entry is added to `composition.yaml`. The function falls through to raw-skill loading (no fragments), silently changing the prompt.

**Expected behavior:** `compose_skill` should log a warning when a requested skill is absent from the manifest (falling through to raw is the current behavior). Before shipping Conversation 2, confirm that `planning/plan` is present in the manifest. The fallthrough-to-raw behavior is acceptable for backwards compatibility but must not be silent — a warning log is required.

**Verification:** Call `compose_skill("planning/plan", caps, manifest)` before and after adding the manifest entry; confirm the composed prompt differs and that the pre-entry call logs a warning.

---

## EC-06 — `AGENT_DONE.summary` absent or empty after Decompose run

**Risk:** The CLI agent exits without writing an `AGENT_DONE` event to EVENTS.jsonl (crash, timeout, kill). The supervisor's new code path expects `AGENT_DONE.summary` but finds nothing.

**Expected behavior:** The supervisor must handle a missing `AGENT_DONE` event as a failed run. It must not silently treat a missing result as success. The existing error path for goal run failures must fire.

**Migration risk:** The old path fell through to stdout parsing when `AGENT_DONE` was absent. The new path must not silently succeed where the old one would have produced an empty result. Verify the supervisor raises a clear error if `AGENT_DONE.summary` is not found within the timeout window.

---

## EC-07 — `build_adapter_caps()` called from HTTP path with fields that do not exist in supervisor context

**Risk:** The HTTP path (`editor_render.py`) receives a renderer-side context dict with keys that the supervisor context (`goal_decomposer.py`) never has (e.g., `editor_id`, `artifact_path`). `build_adapter_caps()` that works for both paths must handle sparse contexts gracefully.

**Expected behavior:** `build_adapter_caps(ctx)` uses `.get()` with safe defaults for all optional fields. A missing `executor` defaults to `"single"`. A missing `kind` defaults to `"agent"`. A missing `goal_id` defaults to `None`. No KeyError is raised for any absent optional field.

---

## EC-08 — Dash-safety regression in composed planning/plan prompt

**Risk:** The `planning/plan` skill body starts with `---` (YAML frontmatter or a markdown divider). The composed prompt is passed to the CLI as argv. Claude CLI parses it as an unknown option and aborts.

**Expected behavior:** `_dash_safe_prompt` / `dashSafePrompt` strips leading `---` before the prompt reaches argv. This is already enforced at three call sites. The new Decompose path must pass its composed prompt through the same dash-safety wrapper before spawning the CLI.

**Verification:** Check that the Decompose headless spawn path passes through `_dash_safe_prompt` (Python) or the equivalent TS wrapper. Add a test: compose a planning/plan prompt, prepend `---\n`, verify `_dash_safe_prompt` strips it.

---

## EC-09 — `blocks:` key accidentally renamed to `profiles:` in Gate 2 PR

**Risk:** A builder working on Gate 2 renames `blocks:` to `profiles:` in `composition.yaml` thinking it is part of the cleanup. This breaks all existing skill compositions that reference the `blocks:` key.

**Expected behavior:** Reviewers must reject any Gate 2 PR that touches the `blocks:` key. The rename is Gate 3 only. Add a reviewer checklist item to IMPLEMENTATION_PLAN.md risk register.

---

## EC-10 — `_decompose_consultation()` accidentally modified during conversion

**Risk:** The builder converts all three `_decompose_*` functions instead of just `_planner` and `_plan`. `_decompose_consultation()` uses the FSM path and must not be touched.

**Expected behavior:** `_decompose_consultation()` is unchanged by Conversation 2. The diff for that conversation must show zero changes to that function.

**Verification:** After Conversation 2, run `git diff HEAD -- src/pathly_orchestrator/supervisor/goal_decomposer.py | grep "_decompose_consultation"` — the result should be empty (no lines changed in that function).
