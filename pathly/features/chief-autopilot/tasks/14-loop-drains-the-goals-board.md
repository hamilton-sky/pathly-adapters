# Drain a loop goal's tasks from the goal's own board

Type: task
Status: open
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
