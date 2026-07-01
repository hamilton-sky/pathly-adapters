# Consultation board-scope + board-level planning

## Problem (verified 2026-07-01)

A consultation spawned from the `cli-command-center` feature board created a flat
`pathly/goals/<slug>/` folder and posted the PO artifact to a **new goal-slug-scoped
board** (`scope=studio-climonitorbar-…-3453c9bb`) — *not* the `cli-command-center`
board it was spawned from. Root cause: `build_prompt` derived `feature =
storage_path.name`, and the consultation's storage is routed to `pathly/goals/<slug>/`,
so `<feature>` (used by `comms-post`, context retrieval, telemetry) resolved to the
**slug**. The goal-slug is needed for FSM run isolation, but it must not leak into the
board scope.

This orphans the consultation's outputs from the feature: they land on a throwaway
slug board, so the feature's downstream agents can never retrieve them (semantic +
catalog channels in `retrieve_board_context` are keyed on `(board, scope)`).

## Model (locked)

Two verbs, two altitudes:

- **PLAN** = *board-level*. Read board intent → emit goal cards, each carrying a DAG.
  Goal factory. Rigor: `quick` (dag-sketch) · `full` (plan) · `consultation` (team).
  Maps to decompose `mode`.
- **EXECUTE** = *goal-level*. Drain one goal's DAG. Style: `single` · `loop` · `team`.
  Maps to goal `executor`.

Knowledge (PO/arch/research/design) belongs to the **feature** → posted to the feature
board (its backing files are id-addressed store, not a browsed folder). The plan + DAG
belongs to the **goal** → `pathly/features/<feature>/goals/<slug>/`, the planner's only
human-facing deliverable. Not a "split": two owners (feature vs goal), two homes.

## Changes

### B1 — Board-scope decoupling  ✅ DONE
`build_prompt` computes `board_scope` = the goal's parent scope (via
`get_goal_board_scope(goal_id)`) when `goal_id` is set, else `storage_path.name`.
All board/context/telemetry uses (`<feature>` injection, "Feature:" line, history,
`get_board_scope`, `retrieve_board_context`, code-context) route through `board_scope`;
file paths (`<feature_path>`/`<out_path>`) stay `storage_path`. Backward-compatible:
no `goal_id` ⇒ byte-identical to before.
- `src/pathly_orchestrator/db/queries/comms_messages.py` — `get_goal_board_scope`
- `src/pathly_orchestrator/fsm_compose.py` — `build_prompt`
- `tests/test_fsm_ops.py::test_build_prompt_uses_parent_board_scope_for_goal`

Effect on catalog + semantic retrieval: **fixed**, not broken. Consultation artifacts
now embed + catalog under the parent scope, so the feature's downstream agents retrieve
them. No schema change.

### UI — board-level, target-selectable planning  ⏳ NEXT
Unite the per-goal `GoalDecomposeButton` into the board-level `EvaluateBoardButton`:
- Board header: one **Evaluate / Plan** control. Popover adds **rigor** (quick/full/
  consultation) + **target** (whole board | a specific goal). Whole-board = evaluate/
  propose; specific goal = decompose that goal at the rigor.
- Goal card: **execution-only** — status (planned / needs-plan) + `Execute ▾`
  (single/loop/team). Remove `GoalDecomposeButton` from the card.

### Storage nesting (Phase 2)  ⏳ DEFERRED
Route goal-decompose storage to `pathly/features/<feature>/goals/<slug>/` (3 sites in
`goal_decomposer.py`) + knowledge backing to the feature board-artifact store. Separate
change; B1 already fixes the board-scope bug independent of file location.
