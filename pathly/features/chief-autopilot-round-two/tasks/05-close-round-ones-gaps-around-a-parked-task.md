# Close round one's gaps around a parked task

Type: task
Status: open
Blocked by: —
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/queries/task_waits.py, src/pathly_orchestrator/supervisor/run_task_outcome.py, src/pathly_orchestrator/supervisor/task_wait_outcome.py, src/pathly_orchestrator/supervisor/orchestrator_stage.py, src/pathly_orchestrator/supervisor/orchestrator.py, src/pathly_orchestrator/supervisor/task_proof.py, tests/dag_goals/test_loop_park_gaps.py (new), src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

Five minors carried in round one's HANDOFF lines (06, 12, 14, 09), each a misreport or a lost
answer around a parked task. They come first because tickets 06 and 07 park many more tasks.

1. **The park and answer race.** An answer posted between `open_questions_by_run` and `park_task`
   finds no blocked task to free (`release_on_answer` runs at the answer's write), so the task stays
   parked on an answered question. New `task_waits.park_and_recheck(conn, task_id, question_ids)
   -> str` (`parked`, `released` or `not_parked`): `park_task`, then, when every id is answered
   now, `release_waiting_tasks` for them. Use it in `run_task_outcome._free_unfinished` and
   `task_wait_outcome.park_if_asked` in place of the bare `park_task`. A released task still
   counts as a wait (`waits + 1`, no attempt spent) and keeps the answers in
   `answered_questions`.
2. **`park_task` returning False completes the task silently** (`park_if_asked`). Log a warning
   naming the task, its current `task_status` and the question ids; the handler then goes on as
   it does today.
3. **`task_proof` proves an asking attempt.** In `task_proof.wrap`, before the proof of a
   `sched-<task>#<n>` spawn that reported success, read `task_waits.open_questions_by_run` for the
   run id: when it has any, return the outcome unproven (no floor scan, no check runs, no
   `TASK_PROOF` event); the scheduler then parks it. A failure to read leaves the proof as today.
4. **"continuing to the next stage" before a loop run parks.** `orchestrator.py`'s RUNNER_WARNING
   for a stage that "reported failure ... but exited cleanly" is not broadcast when the stage
   result's `error` starts with `waiting_for_answer` (the drain's merged result,
   `fan_out._merge_drain_result`). `orchestrator.py` is at 399 lines: keep the change to the
   condition.
5. **A parked goal-loop run writes no `RUN_OUTCOME`**, so `GET /runs/<id>` and `GET
   /chief/notices` show `error: null`. Where `orchestrator_stage._resolve_stage_supervised` ends
   the run on `take_run_waits`, append `RUN_OUTCOME {run_id: <the goal-loop run>, outcome:
   failed, error: waiting_for_answer}` to the run's storage (reuse
   `run_task_outcome._record_run_outcome`), so `run_history_read._run_outcome` reads it.

## Not in this ticket

- Parking on a question to a role: tickets 06 and 07 (they use `park_and_recheck`).
- `chief_session_runs` limit and pruning: ticket 09.

## Done when

- `python -m pytest tests/dag_goals/test_loop_park_gaps.py -q -p no:cacheprovider` passes and
  covers: an answer written after the open-questions read and before the park leaves the task
  `pending` with `answered_questions` and `waits` 1 (single and loop paths); a `park_task` that
  returns False logs a warning naming the task (caplog); a loop attempt that asked and reported
  success writes no `TASK_PROOF` and runs no check; a goal-loop run that parks broadcasts no
  "continuing to the next stage" RUNNER_WARNING; `GET /runs/<id>` of the parked goal-loop run
  shows `outcome: failed`, `error: waiting_for_answer`.
- All existing tests under `tests/dag_goals`, `tests/runner_supervisor` and `tests/fsm_flows` still pass.

```check
$ python -m pytest tests/dag_goals/test_loop_park_gaps.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/runner_supervisor tests/fsm_flows -q -p no:cacheprovider
exit 0
```

## Reference

- `/mnt/project-files/chief-autopilot/handoffs.md` (read-only: HANDOFF 06, 12, 14, 09)
- round one `pathly/features/chief-autopilot/tasks/12-park-and-resume-loop-tasks.md` (Answer)
- round one learnings (12): driving a goal-loop run in a test

## Answer
