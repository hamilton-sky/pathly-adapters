# Park a task on the question its agent asked, and resume it with the answer

Type: task
Status: open
Blocked by: 05
Test first: yes

Spike S5: a goal-run agent posted a board `question` and exited; nothing waited for the answer,
and when the person answered through the chief, no agent received it. Only the FSM loop's
single-stage states wait for a question (`supervisor/orchestrator.py` → `interactions._await_agent_question`,
for a denied `AskUserQuestion`); a board question from an executor run is never connected to its
task.

At the end of an executor-owned run (the lookup from ticket 05), find the `question` rows that
run posted (the run token on the post names the run: `run_tokens.run_id`; if posts do not record
it yet, record the run id on the row when a run token posts a `question`) that are still
unanswered. For each task still `in_progress` with `claimed_by` this run:

- set `task_status='blocked'` and `fail_reason='waiting_for_answer:<question id>'` (a JSON list
  of ids for several), without counting an attempt;
- the run's outcome is `failed` with `error: "waiting_for_answer"` (ticket 05's override, a
  distinct error).

When a question is answered (`db/queries/comms.py::answer_question`, used by `POST /comms/answer`),
each task blocked on it with no other open question goes back to `pending`. When such a task is
next claimed, `supervisor/task_prompt.py::build_task_prompt` adds a short block with each
question and its answer text (only the answered ones from its reason).

A task deleted in between: the answer is stored, nothing else changes.

## Not in this ticket

- Starting the task again: the person, the chief, or round four's driver starts the goal.
- Routing a question to another agent: round two.

## Done when

- `python -m pytest tests/dag_goals/test_task_waits_for_answer.py -q -p no:cacheprovider` passes
  and covers: a run that posted a question and ended with its task `in_progress` leaves the task
  `blocked` with the reason and the run failed with `waiting_for_answer`, and no attempt counted;
  answering makes the task `pending`; with two questions the task waits for both; the next prompt
  for the task holds the question and answer text; answering after the task was deleted stores
  the answer and raises nothing.
- All existing tests under `tests/dag_goals` and `tests/comms_board` still pass.

```check
$ python -m pytest tests/dag_goals/test_task_waits_for_answer.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/comms_board -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("How a waiting task is marked", "Which task asked")
- spike19-part-b-report.md § 5
- `src/pathly_orchestrator/http_server/blueprints/comms/messages_crud.py::comms_answer`,
  `src/pathly_orchestrator/supervisor/task_prompt.py`

## Answer
