# Drain a loop goal's tasks from the goal's own board

Type: task
Status: resolved
Blocked by: 12
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/fan_out.py, tests/dag_goals/test_loop_drains_goal_board.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

Found while building ticket 09. A chief posts its goals and tasks on the project board
(`board: project`, `scope: <project root>`), as its Operator text says. A `loop` goal there runs
the `goal-loop` flow, but `supervisor/fan_out.py::_drain` hardcodes `board = "feature"` while
`_frontier_scope` resolves the scope to the project root. So `drain_frontier` asks for ready tasks
on `("feature", <root>)`, finds none, the task stays `pending` with no attempts, the stage's
feedback rounds spawn builders with no task, and the run ends `error`. A feature-board loop goal
works today.

1. `_drain` takes the board from the goal's own row (`comms_messages.board` for `state.goal_id`,
   the same column `goal_executor` reads), and keeps `"feature"` when the run has no goal or the
   row has no board. The same board goes to `_resolve_isolation`.

## Not in this ticket

- A `RUN_OUTCOME` row for a parked loop run (its `GET /runs/<id>` error stays null).

## Done when

- `tests/dag_goals/test_loop_drains_goal_board.py` passes with tests that a goal-loop run for a
  `loop` goal posted on the project board claims its ready task as `sched-<task>#1`, and that a
  feature-board loop goal still drains as before.
- The existing tests under `tests/dag_goals` still pass.

```check
$ python -m pytest tests/dag_goals/test_loop_drains_goal_board.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals -q -p no:cacheprovider
exit 0
```

## Reference

- `src/pathly_orchestrator/supervisor/goal_executor.py` (reads the goal row's board)
- `tests/dag_goals/test_loop_task_waits.py` (a real goal-loop run in process)

## Answer

Work started at commit `872fce37b9768f756898fd1583d45a21a1ec8d82`.

- **Built**: `src/pathly_orchestrator/supervisor/fan_out.py` (new `_goal_board(goal_id)`; `_drain`
  uses it for `drain_frontier` and `_resolve_isolation` instead of the hardcoded `"feature"`),
  `tests/dag_goals/test_loop_drains_goal_board.py` (new, 2 tests), `src/pathly_orchestrator/CLAUDE.md`
  (the fan-out diagram and the `fan_out.py` file-map entry name the board source),
  `tests/INDEX.md`, `tests/dag_goals/INDEX.md` (regenerated).
- **Proof**:
  - `python -m pytest tests/dag_goals/test_loop_drains_goal_board.py -q -p no:cacheprovider` →
    `2 passed`, exit 0. At the test-only commit it failed for the right reason: the project-board
    goal's spawns were `project/goals/goal-…-fb1/fb2/fb3` (feedback builders with no task), not
    `sched-<task>#1`; the feature-board test passed there too.
  - `python -m pytest tests/dag_goals -q -p no:cacheprovider` → `255 passed`, exit 0.
  - Lint pieces: `black --check src/ tests/` clean, mypy on `fan_out.py` clean, `check_file_size.py`
    "none new, none grown" (fan_out.py 321 lines), `check_no_mirror_reads.py` OK,
    `gen_test_index.py --check` up to date, `lint-imports` 1 kept 0 broken, bandit on fan_out.py
    clean.
- **Decisions**: reused `db/queries/comms_goal_fields.get_goal_board_scope` (the same
  `comms_messages.board` column `goal_executor` reads; also requires a live `type='goal'` row), so
  no new SQL. It returns None when board or scope is empty, which maps to `"feature"` as the ticket
  asks; a lookup error also falls back to `"feature"` (logged at debug), matching
  `_frontier_scope`'s best-effort style. Only the board comes from the row; the scope still comes
  from `_frontier_scope` (it already resolves the project root for a project-board goal). The tests
  drive the real `start_goal_run(executor_override="loop")` path, not `start_run` directly, so the
  run's topic and board scope are what a chief's goal really gets.
- **Shortcuts taken**: none.
- **For later tickets**: ticket 09 can now run a chief's project-board `loop` goal; its first
  spawn is `sched-<task>#1`. Ruff's UP rules flag 6 pre-existing `Optional[...]` uses in
  `fan_out.py`; untouched (not in this ticket, and ruff is not in the Lint chain).
