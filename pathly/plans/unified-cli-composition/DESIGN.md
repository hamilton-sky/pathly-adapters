# Unified CLI Composition — Design (PO → Architect → Designer)

> Refined from [BRIEF.md](BRIEF.md) by the three Pathly role contracts. Implementation-ready.
>
> **Bigger picture:** the fragment profiles below are the two ends of one dial. Every agent
> spawn carries a context, and `goal_id` presence selects the profile: **standalone**
> (pure transforms — `client-file-output` + `artifact-transform`, this doc's P0) vs
> **goal-backed** (`comms-post` + `catalog-pull` + `board-start-context` + `task-dag-post`).
> See [ORCHESTRATION_MODEL.md](ORCHESTRATION_MODEL.md) for the two-axis model and the
> spawn-context that unifies single/loop/team/flow execution.

---

## Implementation status (2026-06-28)

**P0 — BUILT and merged to master.** The standalone-transform half of the design is live:
- `POST /skills/compose` endpoint + `services/skillCompose.ts` client seam.
- Fragments `client-file-output` + `artifact-transform`; skills `development/{summarize,analyze,split}`.
- artifact **Summary** → composed prompt + **file-based capture** (the codex/claude stdout-tail bug
  is fixed at the source); editor **Analyze/Split** route through composition + honor the `ERROR:`
  contract. Models left on their own path (deferred — [[project_models_separate_from_cli]]).

**Summary sub-features added on top of P0 (also built):**
- **Retrieval:** the summary is now embedded (`description + summary`), agents post BOTH a real
  description and a section summary (`comms-post` fragment + `/comms/post` accept a `summary`).
- **Depth styles** Gist / Topic-map / Detailed — 3 `development/summarize*` skills, per-artifact
  (`summary_style` column + `/style` endpoint), selectable in the gear.
- **Special request** free-text note, per-artifact (`summary_note` column + `/note` endpoint),
  appended to the prompt.
- **Confirm-preview modal** on Summarize (Cancel/Run), like Decompose; SVG summary badge; AI summary
  shown in the expanded card; copy-content + copy-path icons; ANSI-escape strip on the fallback path.
- **Output-format contracts (single-sourced):** each depth's exact output shape lives in
  `core/templates/summary/{gist,topic-map,detailed}.md`; the `development/summarize*` bodies are
  agnostic intent + a `<summary_format>` placeholder that `/skills/compose` substitutes (keyed by
  skill); `GET /skills/summary-format/<style>` serves the same file to the Studio depth-picker
  preview (rendered via `MarkdownRenderer`, with a style-name header) — so the shape every CLI fills
  and the shape the user previews can't drift.
- **Description rewrite:** summarize emits a structured `## Description` + `## Summary`. The
  Description (1–2 sentence context) overwrites the artifact's **message text** (the card's
  Description; `apiEditMessage` → `/comms/edit`); the Summary body → `comms_artifacts.summary`
  (`useResummarize` parses + dual-saves, description edited first so the summary re-embed sees it).
  Always-overwrite policy; non-compliant output (no `## Description`) leaves the message text alone.
- **Capture cleanup:** the `.summary` file-capture handoff is `.gitignore`d (`*.summary`) and
  deleted after the host reads it into the DB (delete-after-read — summaries only; the editor's
  user-facing `.analysis`/`.draft` keep their own accept/reject lifecycle).

**NOT yet built (the next work):**
- **P1 — goal-backed profile:** fragments `board-start-context` + `task-dag-post`; convert goal
  **Decompose** to a composed `development/decompose` skill; convert `drain-dag` + loop **board-I/O
  surface** only.
- **Solution C (two-lane boundary) + the spawn-context flag** (`goal_id` present → board-backed
  profile) + the naming fixes (`interactive=True` default, passive-FSM-named-as-orchestrator).
- **Plan-type-agnostic decomposer** (planner/consultation produce generic DAGs: coding, research, …).
- P2/P3: migrate server/FSM actions to file capture; `context-limit-contract`; `agent-output-redirect`.

> ⚠️ Live only after the FSM server is restarted with this code (the client falls back to the old
> path until then) + `pathly-setup claude --apply --repair` to sync the new fragments into adapters.

---

## Scope

### Decisions

**Action taxonomy — pure transforms vs board agents.** Two classes, divided by primary product:

| Class | Actions | Product | Composes |
|---|---|---|---|
| **Pure transform** | artifact Summary, editor Analyze, editor Split | A derived file the user opens | `client-file-output` + `artifact-transform` (+ `progress-logging` default) |
| **Board agent** | goal Decompose, goal-execute loop, drain-dag | Board rows other agents consume | board-I/O fragments only (see Architecture) |

The dividing line is whether the action mutates board lifecycle state (tasks, goal frontier, queue) or merely derives a sibling file. This is settled — `_decompose_planner` (`goal_run.py:486-509`) literally POSTs `type=task` rows under a `goal_id`; Summary/Analyze/Split each emit exactly one derived file with no stage/queue/AGENT_DONE notion.

**Pure transforms do NOT post a new board `artifact` message.** They compose `client-file-output` + `artifact-transform` only — never `comms-post`. Discoverability is handled by each action's *existing* surface: Summary writes back onto the existing `comms_artifacts` row via `apiSetArtifactSummary` (`summarizeArtifact.ts:67`); Analyze/Split produce sibling files (`.analysis` / `.split.draft`) the editor surfaces inline as Report/Diff. Adding a `comms-post` would create orphan board rows with no goal/stage context. *Connection-uniformity (same composition primitive + same capture contract) is the goal, not side-effect-uniformity.*

**The markdown-editor surface IS in scope** — narrowly. Analyze and Split route their prompt through `compose_skill` and adopt the fragment-defined file contract. Their existing write-then-poll mechanism (`useEditorAgentActions.ts:13-20`, `pollForFile`) is the *reference implementation* the thesis is lifted from and is kept unchanged. Their bespoke prompt-builders (`buildAnalyzePrompt`/`buildSplitPrompt`) and their pill UX are NOT redesigned — only prompt *assembly* changes.

**The goal-execute loop executor gets board-I/O conversion only**, never the loop body. The frontier control flow (`_run_loop` / `scheduler_loop`) stays Python-owned. Same carve-out as drain-dag: a polling loop has no single AGENT_DONE moment and no feedback-file gate, so the one-shot fragments (`completion-report`, `scout-choreography`, `feedback-protocol`) must not be composed onto it.

**Naming: fragment · skill · profile.** Three layers, one word each. A **fragment** is an atomic reusable prompt block (`fragments/*.md`); a **skill** is the task body ("what to do"); a **profile** is the context-selected fragment bundle ("how it connects to Pathly") — `standalone-transform` (the P0 pure-transform set) vs `goal-backed` (the P1 board set). The composed prompt is `skill body + defaults + profile[context] + skill's own fragments` (deduped, cap-gated). This promotes today's `blocks:` manifest key to `profiles:` and turns the standalone/goal-backed choice into a manifest lookup keyed by `goal_id` presence rather than a code branch — see Architecture › Naming. Fragments cluster by role (board / capture / lifecycle / delegate) as a documented convention; a role-prefix file rename is deferred (the fragment set still grows through P1).

**Skills are agnostic; ALL Pathly connection lives in fragments.** A skill body is the task ("what to do") with ZERO board/FSM/endpoint references; the profile's fragments are the *only* thing that wires an agent to Pathly. Audit (2026-06-28) of skill bodies carrying concrete board calls — the active violators are the three RAW stage skills: `development/drain-dag` (entire loop body is `/comms/*` — handled by P1c: board-I/O → fragments, loop body stays raw), and `team/architect` + `team/research` (each bakes ONE `curl POST /comms/post` artifact post in-body → small `comms-post` extraction, P1e). In-manifest stage skills were already body-reduced when converted (the atomic rule), and utility/control skills (`log-*`, `fsm-call`, `commit`, `go`, `pause`) are operational scripts whose job IS the call — both out of scope. Deeper note: architect/research also carry FSM-stage orchestration (`complete-stage`, `log-phase`, `spawn`, pause) in-body; making FSM-*stage* skills fully FSM-agnostic is a larger architectural change tracked separately (P3+), NOT P1.

### In scope

- A server-side composition seam reachable from client actions, so Summary, Analyze, Split, and Decompose all assemble their prompt through the same fragment-composition primitive as server/FSM actions.
- Two P0 fragments: `client-file-output` and `artifact-transform`.
- Convert artifact Summary from stdout-tail capture to file-based capture (fixes the codex-chrome / claude-flattening summary bug as a side effect).
- Route editor Analyze and Split prompts through composition; keep their write+poll capture.
- Convert goal Decompose from the hand-coded Python POST loop to a composed **narrow decompose skill** + board fragments (see Architecture — *not* `planning/plan`).
- Two P1 fragments: `board-start-context` and `task-dag-post`.
- Convert drain-dag and the goal-execute loop's **board-I/O surface only**.
- Establish file-based result capture as the single capture contract across the converted client actions.

### Out of scope

- A new board `artifact` POST for the transform set (their output is surfaced by existing channels).
- Full conversion of any polling-loop body — `completion-report`/`scout-choreography`/`feedback-protocol` are never composed onto loop executors.
- Redesigning the editor prompt-builders or the client progress UX language beyond what §UX defines.
- P2/P3 fragments (`context-limit-contract`, `agent-output-redirect`) and the remaining raw board skills (`team/architect`, `team/research`).
- Migrating server/FSM actions (Evaluate, single-run, team-execute) onto file capture — they use `AGENT_DONE.summary` authoritatively; revisit in a later phase.
- Changing the `skill_composition` DB-override semantics or the `composition.yaml` format.

### Acceptance criteria

1. Each of the four converted client actions (Summary, Analyze, Split, Decompose) obtains its prompt by calling `compose_skill` against a manifest entry — **zero** remaining call-sites send a bare hand-built prompt string to the CLI for these actions.
2. The three pure transforms compose **exactly** `client-file-output` + `artifact-transform` (plus the `progress-logging` default) and do NOT compose `comms-post`; verified by inspecting each composed prompt.
3. All three pure transforms capture via file-write-then-poll using the naming + ready-trigger defined in `client-file-output`; the stdout-tail path for Summary is removed and the codex/claude summary-quality bug is no longer reproducible.
4. Summary's derived output remains discoverable via the existing `comms_artifacts` summary writeback (no new orphan board message).
5. Goal Decompose composes the narrow decompose skill + `board-start-context` + `task-dag-post`; the hand-coded POST template in `goal_run.py` is removed; a decompose run shows board context in its prompt and posts standard `type=task` rows under the `goal_id`, preserving the existing "do not run the planning workflow" tightness.
6. drain-dag and the goal-execute loop compose ONLY board-I/O fragments and demonstrably do NOT receive `completion-report`/`scout-choreography`/`feedback-protocol`; the frontier loop body is unchanged.
7. A markdown-editor Analyze/Split run and a Command-Center Summary run, given the same source file, both resolve their prompt through the **identical** `compose_skill` entry point.
8. Each converted skill has a `composition.yaml` entry and is DB-overridable via `skill_composition`; a skill absent from the manifest still loads raw (no regression — `compose_skill:247-248`).
9. When the FSM/compose endpoint is unreachable, every transform falls back cleanly to its current bare builder (no hard dependency); covered by an endpoint-down test.

---

## Architecture

### Composition seam — server-side endpoint, no TS mirror

**Decision: add `POST /skills/compose` to the skills blueprint**, sibling to the existing `/skills/preview` (`blueprints/skills.py`) which already calls `compose_skill` server-side. No TypeScript mirror of `compose.py`.

Rationale (resolving PO's deferred Q1): the manifest is DB-overridable via `load_effective_manifest` + the `skill_composition` table (`compose.py:63-92`); a TS mirror would have to re-read those rows over HTTP anyway, buys nothing, and forks a second source of truth. Fragment bodies, `_strip_leading_frontmatter`, and adapter-caps gating live only in Python — mirroring them is the exact three-copy maintenance trap CLAUDE.md flags for dash-safety. The renderer already round-trips to `127.0.0.1:8765` constantly, so one more POST is free. The renderer keeps `dashSafePrompt` as a belt-and-suspenders client guard only.

**Endpoint contract — `POST /skills/compose`:**

```
Request:  { "skill": "development/summarize",
            "adapter": "claude",
            "transform": { "source_path": "...", "out_path": "...", "kind": "summary|analysis|split" } }
Response 200: { "prompt": "<dash-safe composed markdown>", "skill": "...", "composed": true }
```

- `skill` = manifest key (required). `adapter` resolves caps via `adapter_caps_for` (default `"claude"`).
- `transform` = optional dict whose keys are injected as prompt vars (reuse the same `_inject_prompt_vars` path `/skills/preview` uses) so `client-file-output`/`artifact-transform` render concrete paths.
- Uses `load_effective_manifest(project_root)` so DB overrides apply. A skill absent from the manifest returns its raw body with `composed: false` (no regression). Server applies `_strip_leading_frontmatter`; renderer still applies `dashSafePrompt` in `buildHeadlessArgv`.
- **Skip-if-down:** if the endpoint is unreachable, the client falls back to its current bare `buildSummarizePrompt`/`buildAnalyzePrompt`/`buildSplitPrompt`. Composition is an enhancement layer, never a hard dependency. The client wraps the fetch in try/catch and logs a one-line warning.

**Two physical composition callers** (resolving the loop-routing question, architect Q4):

| Caller | Actions | Mechanism |
|---|---|---|
| Renderer (TS) | Summary, Analyze, Split | `POST /skills/compose` → composed prompt → CLI argv |
| Supervisor (Python) | Decompose, goal-execute loop, drain-dag | `compose_skill` / `compose_block` called in-process |

The renderer owns transform spawns; the supervisor owns board-agent spawns. Each calls composition from the layer it already lives in — no routing Python-built prompts back out through HTTP.

**Client seam placement:** add a single async helper `composeClientSkill(skill, adapter, transform): Promise<string | null>` in a new `services/skillCompose.ts` that POSTs the endpoint and returns the prompt (or `null` on failure). `summarizeArtifact` and `useEditorAgentActions` call it and substitute the bare builder only on `null`.

### New-fragment contracts

**`client-file-output` (P0)** — vars `{out_path}`. Pure file I/O, no network. Body instructs: *"Write your entire result to EXACTLY this path: `{out_path}`. Write the file as your FINAL action and write it ONCE. Do not print the result to stdout — stdout is discarded. When the file exists and is non-empty, you are done."* Ready-trigger = file exists AND non-empty (matches `pollForFile`, 5 tries × 600ms). Uniform error contract: *"If you cannot produce the output, write a single line beginning `ERROR:` to `{out_path}` so the host surfaces it."* The fragment carries **no hardcoded extension** — it only echoes the `{out_path}` it is handed (the renderer is the path authority, see below).

**`artifact-transform` (P0)** — vars `{source_path, out_path, transform_kind}`. No board POST, no `comms-post`. Body: *"Read `{source_path}` ONCE. Derive a `{transform_kind}`. Write the derived result to `{out_path}`. RULES: never modify `{source_path}`; never read `{out_path}` back as input; the source is read-only, the output is write-once."* Composed together with `client-file-output` for all three transforms. The never-re-read-own-output rule is **prompt-only in P0/P1** (mechanical host refusal is a P2 hardening, noted in Open questions) — confirmed low-risk because the host poller only ever reads the derived path and nothing currently feeds a derived file back as source.

**`board-start-context` (P1)** — vars `{board, scope, goal_id?}`. A thin instruction wrapper over an already-rendered context block. In practice the supervisor pre-renders the block via `comms_context.board_context_for` and appends it (same as `board_run.py`), so the fragment just says: *"At START you are given the board context block below (governance + open tasks + recent + catalog). Read it once; do not re-poll."* **Skip-if-down:** if the FSM is unreachable the pre-rendered block is simply empty/absent and the agent proceeds with no board context — never blocks (mirrors the `board_run` `context=''` path).

**`task-dag-post` (P1)** — vars `{board, scope, goal_id}`. Declarative task/sub-tree post. Body instructs one POST per task:

```
POST http://127.0.0.1:8765/comms/post
{ board, scope, from, type:'task', goal_id, text:<title>, stage:<implement|...>,
  status:'pending', parent_id?:<task id>, depends?:[ids] }
```

Matches the hand-coded shape in `_decompose_planner` (`goal_run.py:493-508`); `parent_id`/`depends` are the DAG edges read by `get_ready_tasks`. **Skip-if-down:** posts fail individually; a failed post does not corrupt the board, and re-decompose is guarded by the `already_decomposed` check (`goal_run.py:420-425`).

### Naming: fragment · skill · profile (and the `profiles:` refactor)

| Layer | Name | Means | Example |
|---|---|---|---|
| atomic block | **fragment** | one reusable prompt block (`fragments/*.md`) | `comms-post`, `client-file-output` |
| task body | **skill** | "what to do" — the agent's task | `development/summarize`, `team/build` |
| context bundle | **profile** | "how it connects to Pathly" — fragments chosen by spawn context | `standalone-transform`, `goal-backed` |

One equation governs every spawn:

```
composed = skill (body)
         + defaults              (always: progress-logging)
         + profile[context]      (the wiring, selected by goal_id presence)
         + skill's own fragments (intrinsic extras)
           └─ dedup, then drop cap-gated (e.g. spawn-rules if !can_spawn)
```

**`blocks:` → `profiles:`.** Today the manifest carries a `blocks:` map (`full-build`, `lite-build`, `review-strict`) resolved by `compose_skill_with_block`; it *also* copy-pastes `[client-file-output, artifact-transform]` across all five transform skills; and the goal-backed fragment set lives in a `goal_id` code branch. These are the same concept three times. Rename `blocks:` → `profiles:`, add `standalone-transform` + `goal-backed` as first-class entries, and have each transform skill reference `profile: standalone-transform` instead of repeating the list. The resolver then selects the profile by context — `goal-backed` when `goal_id` is present, else the skill's declared profile — one lookup, no scattered `if goal_id:`. Backward-compatible: `compose.py` reads `profiles:` and still accepts `blocks:` as an alias for one release.

**Fragment role convention** (naming only; file rename deferred): `board` (comms-post, catalog-pull, board-start-context, task-dag-post) · `capture` (client-file-output, artifact-transform, completion-report) · `lifecycle` (progress-logging, feedback-protocol) · `delegate` (spawn-rules, scout-choreography).

### Manifest keys & disk bodies

`compose_skill`/`validate_composition` require a real `core/skills/<key>.md` to exist (`validate_composition:299`). Therefore:

- **Three new transform bodies + manifest entries:** `development/summarize`, `development/analyze`, `development/split`. Bodies are tiny (one line: "read the source, produce the {kind}"); the contract comes from the two fragments. Each entry: `[client-file-output, artifact-transform]` (the `progress-logging` default is automatic).
- **Decompose: a NEW narrow `development/decompose` body** — **NOT** `planning/plan`. This resolves the PO↔architect conflict in the architect's favor. The current `_decompose_planner` is deliberately self-contained ("No planning skill is loaded — the agent skips the feature-planning workflow", `goal_run.py:479-509`). Composing the heavy `planning/plan` would make the agent author USER_STORIES instead of just POSTing tasks. The new body preserves the existing tight instruction ("POST 3-7 tasks, do NOT create plan files or run the planning workflow"); the board posting and context move into fragments. Entry: `[board-start-context, task-dag-post]`.
- **drain-dag: a NEW `development/drain-dag` manifest entry** (it is currently intentionally raw). Entry composes `[comms-post, task-dag-post, catalog-pull]` and must NOT compose `completion-report`/`scout-choreography`/`feedback-protocol`/`spawn-rules`.

Each manifest entry lands **atomically** with its disk body in the same PR — adding an entry without the `.md` makes server-start `validate_composition` throw. After each, run `pathly-setup claude --apply --repair` + `python -m build` to sync adapters.

### Derived-file naming — single source

The **renderer is the path authority.** It already computes `draftPath = forFile + '.split.draft'` and `analysisPath = forFile + '.analysis'` (`useEditorAgentActions.ts:77,143`); Summary uses the artifact path. The renderer computes `out_path`, passes it in the `transform` payload, the fragment echoes `{out_path}` verbatim, and the poller reads the same `out_path` it sent. No naming rule is hardcoded inside the fragment, so prompt text and poll path can never drift.

### drain-dag plan (and the identical loop carve-out)

`development/drain-dag` composes exactly `progress-logging` (default) + `comms-post` (status narration) + `task-dag-post` (queue ops) + `catalog-pull` (optional mid-loop `context_refs` hydration). It MUST NOT compose `completion-report` (a polling loop has no single AGENT_DONE — it drains N tasks, each completed via `/comms/tasks/complete`), `scout-choreography` (no one-shot three-phase gather), `feedback-protocol` (no feedback-file gate on a frontier), or `spawn-rules` (drain-dag IS the self-loop). **The loop body / frontier control flow stays raw and Python-owned** — composition supplies only the board-I/O fragment block.

The goal-execute loop (`_run_loop`) follows the **identical** rule: rather than routing a whole skill through composition, the supervisor injects `compose_block(['board-start-context','task-dag-post','comms-post'], adapter)` into its Python-built per-task prompt. `compose.py` already supports this via `resolve_block`/`compose_skill_with_block` (`compose.py:184-229`). Same shape, same carve-out, Python-side not HTTP. This requires adding a `loop-board-io` (or equivalent) entry under the manifest's `blocks:` key.

---

## UX & Feedback

### The one feedback model

**One feedback language: the in-place segmented action pill** (`shared/ActionPill` for actions with an openable artifact result; `shared/RunPill` for run/stop-only actions), anchored on the control that launched the action. Not board status posts, not toast-as-primary, not a status badge. Every CLI action renders the same four-state pill on its own trigger:

`idle` (verb label) → `running` (verb + live elapsed clock, gear swaps to Stop) → `success` (`Done`, plus a result chip when there is an artifact to open) → `error` (`Error`, red).

This is already the de-facto standard (editor Analyze/Split, board Evaluate, Goal Run, Goal Decompose). Two non-conforming surfaces get pulled in: **artifact Summary** (toast-only today → gets a pill keyed by `artifactId`); the **loop/drain-dag** board agents keep posting board status, but those posts are agent-to-agent audit telemetry, not the user's progress surface — the human reads the goal's one RunPill.

**Rule:** board `comms-post` status lines are agent-to-agent governance telemetry and stay visible in the board feed; the pill is human-to-action feedback. The two coexist and never compete for the user's eye.

**Toasts are demoted to a single-line echo of the pill's terminal transition only**, reusing the two existing categories: `category:'phase_summary'` (info, auto-dismiss ~4s) for start/stop echoes; `category:'agent_done'` (success/error, sticky-ish) for the terminal result. No new toast variants. Progress is NEVER toast-primary — the pill's clock is the progress; a toast is at most a courtesy echo for a user who navigated away. Loop/drain-dag emit at most ONE terminal toast for the whole run (never per iteration).

### Per-action surface

| Action | Progress | Result | Tab = primary feedback? (tab is always visible; pill is primary) |
|---|---|---|---|
| artifact Summary | RunPill on Re-summarize + inline pill on the drop/upload card, keyed by `artifactId`, live clock | Summary prose re-renders on the `comms_artifacts` row (existing writeback) — that IS the result, no chip. `agent_done` toast "Summary ready". | No |
| editor Analyze | ActionPill on Analyze control, clock from `tab.startedAt`, gear→Stop (unchanged reference impl) | Pill→success + **Report** chip opening the `.analysis` view. Echo toast only. | No |
| editor Split | ActionPill on Split control, clock, gear→Stop (unchanged) | Pill→success + **Diff** chip opening the `.split.draft` diff (auto-switches `viewMode` to editor). Echo toast only. | No |
| goal Decompose | ActionPill on Decompose control, clock, gear→Stop | Pill→success; result = `type=task` rows materializing under the goal in the board. `agent_done` toast "Goal decomposed". | No |
| goal-execute single/team | Goal RunPill (clock + Stop) over SSE | Agents' board posts + tasks flipping to complete; no terminal chip. Optional `agent_done` toast at run end. | No |
| goal-execute loop (frontier) | Same single goal RunPill for the whole loop | Tasks flip complete + board artifacts; no per-iteration toasts; one terminal toast at loop end. | No |
| drain-dag (self-loop) | Surfaced through the driving goal's RunPill (no standalone control) | Queue drained + task rows complete; no dedicated toast beyond the goal-run terminal echo. | No |

### Binding UX rules

- **The running clock is the canonical progress signal** and MUST derive from `tab.startedAt`, stamped optimistically BEFORE the spawn await (as `useEditorAgentActions` already does at lines 85/149) so navigate-away-and-back restores accurate elapsed time. Never hold per-run elapsed in React or recompute from `onExit`.
- **Result-as-chip vs result-as-surface:** an openable derived file (Analyze→Report, Split→Diff) gets a result chip; in-place data (Summary→card prose, Decompose/Run→board rows) gets NO chip — the re-rendered surface IS the result. Never invent a chip that opens a modal duplicating the board.
- **The PTY tab is ALWAYS visible — it is just never the *primary* feedback surface.** Every converted action opens a real, visible PTY tab (`aiRouter.ts` reveals it via `openTab`, "like every other CLI-engine spawn", and runner/board stages open one via `TERMINAL_SPAWN`); there is **no hidden/background spawn**. "Headless" here means *app-driven, the PTY exits when the agent finishes* (vs interactive = the human can type and the shell stays open) — it does **not** mean invisible. The user watches the in-place pill, not raw stdout, but the tab is always there (revealed in the monitor bar + as a tab, with Stop). This is *why* fixing Summary's stdout-tail is also a UX fix — stdout was leaking codex chrome into the user-visible result.
- **Uniform error contract across all seven.** Pill→error (red `Error`) + ONE `agent_done` error toast with the reason (`describeAgentFailure` for editor; `"Summary failed: <reason>"`; `"Goal decompose failed: <reason>"`). The `client-file-output` `ERROR:`-line convention must be parsed by the host poller and routed through this SAME path. **This is a required code change:** today `pollForFile` (`useEditorAgentActions.ts:13-20`) treats any non-empty file as success; it must detect a leading `ERROR:` and route to pill-error + the error toast instead of opening a broken result. Do not add a second error UI.
- **Stop** swaps the running segment to a Square (ActionPill) or uses the dedicated Stop (RunPill); stopping closes the tab immediately and resets the pill to idle with a `phase_summary` "stopped" echo. Keep the stale-run reconciliation effect (`useEditorAgentActions.ts:49-59`) for every pill-backed action so a lost exit can't hang the pill.
- **Pill state is keyed by the artifact/goal it ran for** (`forFile` / `goalId` / `artifactId`), never a shared React instance — replicate the existing `mdEditorActions[forFile]` pattern for Summary (key by `artifactId`) and goal runs (key by `goalId`).
- **Conformance test:** any newly added CLI action MUST mount a pill. Result-chip tone is semantic (green = ready/clean, amber = ready-with-attention, e.g. a Split diff with changes) reusing `ActionPill`'s `data-tone`; no new colors. Every pill segment keeps its `aria-label`; the running pill is a real `<button disabled>`, not a spinner-only element.
- **Compact mode** (`ActionPill compact`): at narrow widths (≤200px per the studio responsiveness rule) the elapsed clock drops before the verb, never overflowing the panel.

---

## Phased plan

### P0a — Composition seam (no behavior change)
1. Add `POST /skills/compose` to `blueprints/skills.py`, reusing `compose_skill` + `load_effective_manifest` + the `_inject_prompt_vars` + `_strip_leading_frontmatter` path that `/skills/preview` already uses.
2. Add `services/skillCompose.ts` with `composeClientSkill(skill, adapter, transform): Promise<string|null>` (POSTs the endpoint, returns prompt or `null`).
3. Wire IPC/type declarations if needed. Endpoint exists; nothing calls it yet.

### P0b — Two P0 fragments + three transform bodies
1. Author `fragments/client-file-output.md` and `fragments/artifact-transform.md`.
2. Author thin bodies `core/skills/development/{summarize,analyze,split}.md`.
3. Add three `composition.yaml` entries (each `[client-file-output, artifact-transform]`).
4. Run `validate_composition`; `pathly-setup claude --apply --repair` + `python -m build`.

### P0c — Convert the three transforms to composed + file-capture
1. **Analyze/Split** (`useEditorAgentActions`): swap `buildAnalyzePrompt`/`buildSplitPrompt` for `composeClientSkill(..., {source_path: forFile, out_path: analysisPath|draftPath, kind})`; keep `pollForFile` and the optimistic-`startedAt` pattern; fall back to the bare builder on `null`.
2. **Summary** (`summarizeArtifact`): replace `runJob → result.text` with composed prompt → file `out_path` → poll → **read the derived file** → `apiSetArtifactSummary` with its contents (this read+writeback wiring is new for Summary — call it out in the build prompt). Remove the stdout-tail path.
3. **Teach `pollForFile` the `ERROR:`-line contract** — leading `ERROR:` → pill-error + error toast, not success. Mount the Summary pill keyed by `artifactId`.
4. Each path keeps its bare-builder fallback.

### P1a — Two P1 fragments
1. Author `fragments/board-start-context.md` (thin wrapper over the pre-rendered `board_context_for` block) and `fragments/task-dag-post.md` (the `/comms/post type=task` shape with `parent_id`/`depends`).

### P1b — Decompose conversion
1. Author the NARROW `core/skills/development/decompose.md` body preserving the existing tight "POST tasks, no planning workflow" behavior.
2. Add its manifest entry `[board-start-context, task-dag-post]`.
3. Replace the hand-coded POST loop in `_decompose_planner` (`goal_run.py:486-509`) with an in-Python `compose_skill('development/decompose', adapter)` call (transform/context vars injected); keep the `already_decomposed` guard.

### P1c — drain-dag + loop board-I/O surface
1. Add `development/drain-dag` manifest entry `[comms-post, task-dag-post, catalog-pull]` (NO one-shot fragments).
2. Add a `loop-board-io` block under `blocks:` and inject `compose_block(['board-start-context','task-dag-post','comms-post'], adapter)` into `_run_loop`'s Python-built per-task prompt. Loop body unchanged.

### P1d — Profiles refactor (`blocks:` → `profiles:`)
1. Rename the manifest `blocks:` key to `profiles:`; add `standalone-transform` (`[client-file-output, artifact-transform]`) and `goal-backed` (`[comms-post, catalog-pull, board-start-context, task-dag-post]`).
2. Point the five transform skills at `profile: standalone-transform` (drop the repeated per-skill lists).
3. Teach `compose.py` to resolve a skill's `profile:` and to select `goal-backed` by `ctx.goal_id`; keep reading `blocks:` as an alias for one release (no breaking change).
4. `validate_composition` + `pathly-setup claude --apply --repair` + `python -m build`.

### P1e — Agnostic-skill cleanup (consultation stage skills)
1. Add `team/architect` + `team/research` to the manifest with `[comms-post]` (+ `completion-report` if they should report); delete the in-body `curl POST /comms/post` block so the board post comes ONLY from the fragment — matching the Gap-1 silent-skill pattern (explore/debug/retro).
2. Leave the FSM-stage orchestration (`complete-stage`/`log-phase`/`spawn`/pause) in-body for now — full FSM-agnosticism of stage skills is a separate, larger track (P3+).
3. `validate_composition` + `pathly-setup claude --apply --repair` + `python -m build`.

### Verify
- `node_modules/.bin/tsc --noEmit -p studio/tsconfig.web.json`
- `python -m pytest tests/ -q` + `validate_composition`
- An **endpoint-down test** proving each transform falls back to its bare builder cleanly (ship in the SAME PR as the endpoint call).
- Manual: same source file through editor Analyze and Command-Center Summary both resolve via the identical `/skills/compose` entry point (AC 7); a Summary run no longer reproduces the codex/claude mangling (AC 3).

---

## Open questions

1. **Summary's first-fire pill home.** Re-summarize has a persistent control; the *first* auto-summary fires from the drop/upload handler with no persistent control. **Recommendation (adopt):** render an inline RunPill on the artifact card keyed by `artifactId` for BOTH paths, so the one-feedback-language rule holds with no exception.
2. **Decompose result-toast count ("N tasks").** Requires the client to know the post-decompose task count. **Recommendation (adopt for P1):** generic "Goal decomposed" text; add the count only if a `/comms/tasks` re-fetch is already happening.
3. **`never-re-read-own-output` enforcement.** Prompt-only in P0/P1. Flag a **P2 mechanical guard** (host refuses to feed a `.summary`/`.analysis`/`.split.draft` back as a `source_path`) — cheap later, plumbing-for-a-not-yet-real-failure now.
4. **One pill per goal run regardless of executor.** Confirm `goalRunState` is set for the `loop` executor exactly as for `single`/`team`, so the user never sees two competing progress surfaces.
5. **Board-feed noise vs the pill.** A loop posting many `comms-post` status lines scrolls the feed while the pill sits at `running`. A future collapsed/grouped "agent activity" affordance would keep audit telemetry from drowning human-relevant posts (decisions/artifacts). Out of scope for P0/P1; noted as the cost of keeping board posts as the audit channel.
6. **Windows large-prompt path.** Composed prompts are longer than the bare builders; confirm the new larger transform prompts exercise the PowerShell temp-script path (not `-EncodedCommand`'s ~32KB limit) in `terminal.ts`.

---

Source files for the implementer (all absolute):
- Composition core: `C:/Users/Yafit/pathly-adapters/src/pathly_orchestrator/skills/compose.py` (`compose_skill`, `compose_skill_with_block`/`resolve_block`, `load_effective_manifest`, `validate_composition`)
- Manifest: `C:/Users/Yafit/pathly-adapters/src/pathly_data/core/skills/composition.yaml` (+ `fragments/` dir alongside)
- Endpoint home: `C:/Users/Yafit/pathly-adapters/src/pathly_orchestrator/http_server/blueprints/skills.py` (next to `/skills/preview`)
- Decompose: `C:/Users/Yafit/pathly-adapters/src/pathly_orchestrator/supervisor/goal_run.py` (`_decompose_planner`, lines 463-519; `already_decomposed` guard 415-425)
- Editor capture reference: `C:/Users/Yafit/pathly-adapters/studio/src/renderer/src/components/MarkdownEditor/EditorHeader/hooks/useEditorAgentActions.ts` (`pollForFile`, optimistic `startedAt`, reconciliation effect)
- Summary: `C:/Users/Yafit/pathly-adapters/studio/src/renderer/src/components/CommandCenter/CommsPanel/ArtifactsView/summarizeArtifact.ts`
- New client seam: `C:/Users/Yafit/pathly-adapters/studio/src/renderer/src/services/skillCompose.ts` (to create); dash-safe guard in `studio/src/renderer/src/services/cliEngine.ts`
