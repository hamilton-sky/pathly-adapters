# Park a loop task on its question in the scheduler, and give it the answer

Type: task
Status: open
Blocked by: 06
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/scheduler.py, src/pathly_orchestrator/supervisor/fan_out.py, src/pathly_orchestrator/supervisor/task_wait_outcome.py (new), src/pathly_orchestrator/supervisor/task_prompt.py, tests/dag_goals/test_loop_task_waits.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

The review's B2. Loop tasks are not executor-owned: under fsm-fan-out Phase E they run inside an
FSM stage (`src/pathly_orchestrator/supervisor/task_prompt.py` docstring), the `execute-task` skill tells the agent not to
complete its task, and the scheduler's completion handler
(`src/pathly_orchestrator/supervisor/scheduler.py`, after the worker returns) calls `complete_task`
on success or `task_retry.resolve_task_failure` on failure. So a loop task whose agent asked a
question is either completed over the open question or retried (`retry_task` sets `pending`,
overwriting a park, and spends an attempt from the scheduler's own `task_attempts` count).

In the completion handler, before the success/failure decision, look up the open questions the
task's spawn posted (`db/queries/task_waits.py::open_questions_by_run` from ticket 06, with the
`sched-<task>#N` run id). If there are any, `park_task` it, do not call `complete_task` or
`resolve_task_failure`, do not count the attempt in `task_attempts` (and where the handler derives `current_attempt` from
the stored `attempts`, subtract `waits`), and broadcast a
`task_waiting` event. The next claim gets a new run id (`attempts` only grows, ticket 06), so the
asking spawn's run id is never reused.

Define the goal-loop run's end with a parked task: `src/pathly_orchestrator/supervisor/fan_out.py` must not read the parked
task as a success, and the run ends (`run_history` status `error`, error `waiting_for_answer`)
instead of `require_tasks_done` blocking it with no way forward; the other ready tasks still
drain first. Put the branch in a new `supervisor/task_wait_outcome.py` and call it from
the handler: `scheduler.py` is at 393 lines.

When a parked loop task is claimed again, `build_task_prompt` adds a short block with each
answered question and its answer (from what ticket 06's `release_waiting_tasks` kept).

## Not in this ticket

- Single runs: tickets 05 and 06. Routing the question to an agent: round two.

## Done when

- `python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider` passes and
  covers: a loop task whose fake agent posts a question and exits successfully is parked, not
  completed; one that exits with a failure and an open question is parked, not retried, and no
  attempt is counted; after an answer it is claimed again with a new `sched-<task>#N` run id and
  its prompt holds the question and answer; a goal-loop run with a parked task ends with
  `waiting_for_answer` after draining the other ready tasks; a loop task with no question behaves as before (complete or retry).
- All existing tests under `tests/dag_goals` and `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- review B2
- `src/pathly_orchestrator/supervisor/task_retry.py`, `src/pathly_data/core/skills/development/execute-task.md`

## Answer
