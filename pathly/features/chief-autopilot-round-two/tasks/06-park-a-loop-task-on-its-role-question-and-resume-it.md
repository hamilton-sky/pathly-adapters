# Park a loop task on its role question and run it again in the same drain

Type: task
Status: open
Blocked by: 01, 05
Test first: yes
Level: 3
Touches: src/pathly_orchestrator/db/queries/task_waits.py, src/pathly_orchestrator/supervisor/task_wait_outcome.py, src/pathly_orchestrator/supervisor/task_proof.py, src/pathly_orchestrator/supervisor/fan_out.py, src/pathly_orchestrator/supervisor/consult_wait.py (new), tests/dag_goals/test_loop_role_questions.py (new), tests/dag_goals/test_loop_task_waits.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

Delivery for `loop` goals (spec Decisions, "Park or enrich, per executor": loop parks). The
scheduler, not the agent, completes a loop task, so it holds every attempt that asked a role and
runs it again with the answer; the drain waits for the consults so the run does not stop.

1. New `task_waits.asked_questions_by_run(conn, run_id) -> list[str]`: the ids of
   `open_questions_by_run` (open questions to `human` or `*`) plus every live `question` the run
   posted to a role in `consult_routes.CONSULT_ROLES` (ticket 01), answered or not, oldest first.
   A role question that a role answered while the attempt ran still counts: the attempt did not
   see the answer.
2. `task_wait_outcome.park_if_asked` and ticket 05's proof skip in `task_proof.wrap` read
   `asked_questions_by_run` instead of `open_questions_by_run`. With ticket 05's
   `park_and_recheck`, an already answered question releases the task at once (`pending`,
   `answered_questions`, no attempt counted) and the scheduler's next frontier read claims it as
   `sched-<task>#<n+1>` with `## Answers to your questions` in its prompt
   (`answered_questions_block`).
3. New `src/pathly_orchestrator/supervisor/consult_wait.py` (new):
   `wait_for_consults(task_ids, abort_check, timeout) -> list[str]` polls (an interval a test can
   lower) until no question those tasks wait on has a `queued` or `running` route
   (`consult_routes.pending_routes`), the abort flag is set, or `timeout` passes; it returns the
   ids now `pending`. In `fan_out._drain`, after `drain_frontier` returns with `waiting` tasks of
   which any has a pending route, wait (timeout: the consult spawn's `timeout` plus 90 seconds),
   and when tasks were released drain again and merge the second result into the first (lists
   concatenated, cost summed) before `note_run_waits`. Repeat until nothing is released. Tasks
   that wait on the person stay parked, and the run ends `waiting_for_answer` as before.
4. `tests/dag_goals/test_loop_task_waits.py` asserts round one's "a question to `architect` →
   completed": change that test in place to assert the task is parked (keep the test function).

## Not in this ticket

- Single runs: ticket 07. Routing the question and posting the answer: tickets 02 and 04 (this
  ticket's tests post the answer row directly and fake the route rows).
- Team flow stages: enriched through the board, no new code (spec Decisions).

## Done when

- `python -m pytest tests/dag_goals/test_loop_role_questions.py -q -p no:cacheprovider` passes and
  covers, in a real goal-loop run with a fake spawn (round one learnings 12): an attempt that asks
  `architect` and reports success is parked, not completed; with the answer posted while the
  route is `running`, the drain waits, the task is run again as `sched-<task>#2` in the same run
  with the question and answer in its prompt, and the run ends `success` with `attempts - waits`
  1; an attempt whose role question was answered before it ended is still run again with the
  answer; a route that stays `running` past the wait timeout ends the run `waiting_for_answer`;
  a question handed to the person ends the run `waiting_for_answer` with no wait; an attempt with
  no question is unchanged.
- `python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider` passes with
  the role-question test now asserting a park.
- All existing tests under `tests/dag_goals` and `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/dag_goals/test_loop_role_questions.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Happy path 5-6, § Decisions ("Park or enrich, per executor")
- `src/pathly_orchestrator/supervisor/scheduler.py` (399 lines, read-only here),
  `src/pathly_orchestrator/supervisor/drain.py`

## Answer
