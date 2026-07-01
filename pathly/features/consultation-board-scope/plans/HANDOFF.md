# HANDOFF — consultation board-scope + board-level planning

_Written 2026-07-01. Branch: `shammai/board-design`. Nothing committed — all in the working tree._

Read this + [SPEC.md](SPEC.md) first, then `git status`, then run the verifications below.

---

## The task (what & why)

A consultation spawned FROM the `cli-command-center` feature board posted its PO artifact to a
**throwaway goal-slug board** (`scope=studio-climonitorbar-…-3453c9bb`), not the `cli-command-center`
board it was spawned from. Verified root cause: `build_prompt` did `feature = storage_path.name`,
and consultation storage routes to `pathly/goals/<slug>/`, so `<feature>` (used by `comms-post`,
context retrieval, telemetry) resolved to the **slug**. The slug is needed for FSM run isolation but
must not become the board scope.

## The model (LOCKED with the user)

- **Two verbs, two altitudes.** PLAN = board-level (rigor `quick`/`full`/`consultation` = decompose
  modes `planner`/`plan`/`consultation`); EXECUTE = goal-level (executor `single`/`loop`/`team`).
- **No-split framing** (user's words): knowledge (PO/arch/research/design) belongs to the FEATURE →
  posted to the feature board; the plan+DAG belongs to the GOAL → the planner's goal folder. Two
  owners, two homes — not a fragmentation.
- **UI decision: board-level, target-selectable.** One board-header Evaluate/Plan control with rigor
  + target (whole board | a specific goal). Goal card is execution-only. (User explicitly picked this
  over "board-wide auto" and "lean per-goal trigger".)

## DONE — this task (uncommitted, VERIFIED)

**Backend B1 — board-scope decoupling** (tests: 40/40 in `tests/test_fsm_ops.py` pass):
- `src/pathly_orchestrator/db/queries/comms_messages.py` — added `get_goal_board_scope(conn, goal_id)`
  → `(board, scope)` for a live goal, else None. _(NOTE: this file also carries unrelated pre-existing
  `files=` param work — see "Separate initiative" below.)_
- `src/pathly_orchestrator/fsm_compose.py` — `build_prompt` computes `board_scope` = goal's parent
  scope when `goal_id` set, else `storage_path.name`. All board/context/telemetry uses route through
  `board_scope`; file paths (`<feature_path>`/`<out_path>`) stay `storage_path`. Byte-identical when
  `goal_id` empty.
- `tests/test_fsm_ops.py` — `test_build_prompt_uses_parent_board_scope_for_goal`.
- **Catalog + semantic retrieval:** the scope realignment REPAIRS them (both channels in
  `retrieve_board_context` key on `(board, scope)`) — artifacts now enter the feature's index/catalog.
  No schema change.

**UI — board-level planning** (builder subagent; `tsc -p studio/tsconfig.web.json` exited 0):
- NEW `studio/…/CommsPanel/GoalPlanStatus/` (GoalPlanStatus.tsx + .module.css) — non-interactive pill
  "Not planned" / "Planning…" driven by `goalRunState[goal.id]`.
- NEW `studio/…/CommsPanel/GoalsView/planRigor.ts` — relocated `MODE_OPTIONS`.
- MOD `cards/GoalCard/GoalCardHeader.tsx` — execute-only: `GoalRunButton` when tasks, else `GoalPlanStatus`.
- MOD `GoalsView/EvaluateBoardButton.tsx` + `EvalConfigPopover.tsx` (+ .module.css) — rigor + target
  selectors; whole-board→`runEvaluator`, goal-target→`decomposeGoal(goalId, rigorMode)`.
- MOD `CommsPanel/CommsPanel.tsx` — passes `goals` to `EvaluateBoardButton`.
- DELETED `GoalDecomposeButton/` (component + hooks + DecomposeConfigPopover) — zero remaining importers.

## REVIEW — DONE (5-dimension adversarial workflow, run id `wf_d9d6030e-ff7`)

**16 confirmed (1 major, 7 minor, 8 nit) · 5 rejected.** All 5 rejected were the *integration*
checks PASSING — confirming the core wiring is sound: `goal_id` reaches `build_prompt` on the
consultation FSM path (parent scope resolves), the quick/full (planner/plan) paths already post to
the parent scope, and the UI rigor values match the backend `DecomposeMode`. So the fix works
end-to-end; the confirmed items are edges, the two file-size violations, and stale comments.

### Backend fixes — APPLIED (uncommitted; RE-VERIFY with pytest, the re-run was interrupted)
- **#2 (minor)** `fsm_compose.py` — reverted `feature_dir` for the pipeline-history read back to
  `feature` (the run's own slug identity), NOT `board_scope`. Board writes/context/telemetry stay on
  `board_scope`; history is the run's OWN inter-stage progress. (Earlier full run was 40/40 before this
  edit; the confirm re-run `pytest tests/test_fsm_ops.py -q` was interrupted — run it.)
- **#3 (minor)** `fsm_compose.py` — added a comment documenting that only the FEATURE-tier goal path is
  fully supported (post fragments hardcode `board='feature'`); project/global-tier goal decompose is an
  edge case whose board-tier threading is a follow-up. No behavior change.
- **#10 (nit)** `get_db(project_root or None)` — left as-is on purpose (consistency with
  `goal_decomposer`; the arg is inert). Not a defect.

## DONE — frontend fix-list (2026-07-01; uncommitted; `tsc -p studio/tsconfig.web.json` exits 0)

All 12 confirmed frontend findings resolved. All in `studio/src/renderer`.

Structure (#1, #9) — EvalConfigPopover 208→138, EvaluateBoardButton 176→97, both under the ~150 limit:
- NEW `GoalsView/hooks/useEvaluateBoardButton.ts` (133) — all EvaluateBoardButton state + handlers.
- NEW `GoalsView/BoardEvalConfig/` (.tsx 93 + .module.css) — the whole-board path (lens/engine/preview).
- NEW `GoalsView/GoalTargetConfig/` (.tsx 52 + .module.css) — the goal-target path (rigor/engine/Plan-now).
- `GoalsView/EvalConfigPopover.tsx` now the portal shell + Target selector + branch; `.module.css`
  trimmed to shell + Target row (`.footer`/`.runBtn`→GoalTargetConfig, `.redirectIcon`→BoardEvalConfig).

Behavior (#4, #5, #6, #7, #11, #15):
- **#4** `commsStore.ts` — added `_startGoalWatch`/`_stopGoalWatch`/`_goalBoardParams` (mirror the board
  watchers). Armed on `ok` in `decomposeGoal`/`runGoal`; stopped in `markGoalRunPhase` done/stopped/error
  + `stopGoal`. Polls the goal's parent board-lock; force-completes a stranded "Planning…" pill.
- **#5 + #11** `GoalCardHeader.tsx` — `isPlanning = goalRunState[goal.id] !== 'idle'` (covers running /
  busy / the 3s done-window) so the pill never flashes "Not planned" mid-decompose.
- **#6** `EvaluateBoardButton.tsx` — the heavy `consultation` goal run is now gated behind a `ConfirmModal`
  ("Run a full consultation?"); quick/full still dispatch directly; whole-board keeps its `SendPreviewModal`.
- **#7** `BoardSelect.tsx` gained a `disabled` prop (+ `:disabled` CSS); Target + Rigor selectors are
  `disabled={running}` so a live run can't desync when the popover is reopened.
- **#15** `useEvaluateBoardButton` feeds `goalRunStart[targetGoalId]` into `useElapsedProgress` — the
  Evaluate pill now shows an elapsed clock while a goal decompose runs.

Comments (#8/#16, #12, #13, #14): stale "Decompose control" / "DecomposeConfigPopover" references updated
in `GoalCardHeader.tsx`, `NewGoalButton.tsx`, `EvalConfigPopover.module.css`, `SingleAgentButton.tsx`.

**Verification:** `tsc -p studio/tsconfig.web.json` → 0. Backend `pytest tests/test_fsm_ops.py` → 40/40
(re-run at the start of this session; no Python touched since, so still green).

## DEFERRED — storage nesting (Phase 2, separate change)

Route goal-decompose storage to `pathly/features/<feature>/goals/<slug>/` (3 hard-coded sites in
`src/pathly_orchestrator/supervisor/goal_decomposer.py` lines ~127, ~201, ~272) + knowledge backing to
a feature board-artifact store. B1 fixes the board-scope bug INDEPENDENT of file location, so this is
optional/next, not a blocker.

## SEPARATE INITIATIVE — do NOT conflate

The working tree also contains **pre-existing, unrelated file-claims work** (from before this task):
`supervisor/file_claims.py`, `db/queries/comms_tasks.py`, `db/migrations_incremental.py` (`files`
column), `http_server/blueprints/comms/runs.py`, `supervisor/goal_executor.py`, `tests/test_file_claims.py`,
`tests/test_comms_goals_run.py`, and the `files=` param in `comms_messages.py`/`commsStore.ts`/`commsApi.ts`.
That is the cross-feature collision-protection (#1 toggle + #2 overlap gate) effort — its own verify/commit.
Keep it in a SEPARATE commit from the board-scope work. `comms_messages.py` spans both initiatives.

## Commit policy
Nothing pushed. Never push to master without explicit request; confirm branch first. Suggested split:
(A) board-scope + board-level-planning UI as one commit; (B) file-claims as its own commit.
