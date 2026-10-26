# Park a single run's task on its open question, and free it on any answer

Type: task
Status: open
Blocked by: 05
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/run_task_outcome.py, src/pathly_orchestrator/db/queries/task_waits.py (new), src/pathly_orchestrator/db/migrations_task_waits.py (new), src/pathly_orchestrator/db/migrations.py, src/pathly_orchestrator/db/queries/comms_messages.py, src/pathly_orchestrator/supervisor/task_retry.py, src/pathly_orchestrator/http_server/blueprints/comms/tasks_ready.py (new), src/pathly_orchestrator/http_server/blueprints/comms/tasks.py, src/pathly_data/core/skills/development/drain-dag.md, tests/snapshots/, tests/dag_goals/test_task_waits_for_answer.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

Spike S5: a goal-run agent posted a board `question` and exited; nothing waited for the answer,
and when the person answered through the chief, no agent received it.

New `src/pathly_orchestrator/db/queries/task_waits.py`, shared with ticket 12:

- `open_questions_by_run(conn, run_id)`: `question` rows addressed to `human` (or `*`) whose
  `author_run_id` is the run (`src/pathly_orchestrator/runner/provenance.py::stamp` records it for
  a live run token) and that have no answer yet. "No answer" means: status not `answered` and no
  `type: answer` row with `reply_to` the question (a post through `/comms/post` does not set the
  status). Questions to a role (`to: architect`, the `consult` fragment) do not park a task: the
  agent was told not to block on them, and nothing answers them until round two.
- `park_task(conn, task_id, question_ids)`: `task_status='blocked'`,
  `fail_reason='waiting_for_answer:<id>[,<id>]'`, and `waits = waits + 1` in a new column
  `comms_messages.waits INTEGER NOT NULL DEFAULT 0` (additive migration in a new
  `src/pathly_orchestrator/db/migrations_task_waits.py` (new), wired where the other migrations run). `attempts` is left alone:
  the loop scheduler builds its spawn's run id from it (`sched-<task>#<attempts+1>`), so it must
  only grow. Every attempt-limit check (`task_retry.resolve_task_failure`, ticket 05's limit)
  compares `attempts - waits` with the limit, so waiting never spends a retry.
- `release_waiting_tasks(conn, question_id)`: every task whose reason names the question and has
  no other unanswered one goes back to `pending`, keeping the ids in a `answered_questions` note
  (reason or a JSON field) for the next attempt.

Wire it:

1. In `run_task_outcome.py` (ticket 05), before the
   unfinished check: if the run has open questions and `in_progress` tasks, park each of those
   tasks; the run is failed with `error: "waiting_for_answer"` instead of `task_unfinished`. A run
   with open questions whose tasks are all `done` keeps its outcome.
2. Call `release_waiting_tasks` from the shared write, so every answer path frees the task:
   `db/queries/comms_messages.py::answer_question` (behind `/comms/answer`) and `post_message`
   when `type == "answer"` and `reply_to` is set (a Studio or agent reply, round two's role
   agents).
3. `src/pathly_orchestrator/supervisor/task_retry.py::detect_deadlocks` skips a pending task whose
   dependency chain reaches a task parked `waiting_for_answer`.
4. The answer reaches a single agent where drain-dag reads its work: `GET /comms/tasks?ready=true`
   rows of a task that waited carry `answered_questions: [{question, answer}]` (new helper
   `src/pathly_orchestrator/http_server/blueprints/comms/tasks_ready.py` (new); `tasks.py` is at 413 lines, ratchet baseline), and
   `src/pathly_data/core/skills/development/drain-dag.md` tells the agent to read them before it
   works. Regenerate `tests/snapshots/` if a snapshot composes drain-dag.

A task deleted in between: the answer is stored, nothing else changes.

## Not in this ticket

- Loop tasks: ticket 12 uses the same helpers in the scheduler.
- Starting the task again: the person, the chief, or round four's driver.

## Done when

- `python -m pytest tests/dag_goals/test_task_waits_for_answer.py -q -p no:cacheprovider` passes
  and covers: a single run that posted a question and ended with its task `in_progress` leaves it
  `blocked` with the reason and the run failed with `waiting_for_answer`; three park-and-answer
  cycles leave `attempts - waits` where one claim put it and do not escalate; a question to a role
  (`to: architect`) does not park the task; an answer through
  `/comms/answer` and one through a `type: answer` post with `reply_to` both free the task; with two
  questions it waits for both; a dependent of the parked task is not deadlocked; the ready-tasks row
  of the freed task carries the question and answer; answering after the task was deleted stores
  the answer and raises nothing.
- All existing tests under `tests/dag_goals`, `tests/comms_board` and `tests/install_skills` still
  pass.

```check
$ python -m pytest tests/dag_goals/test_task_waits_for_answer.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/comms_board tests/install_skills -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("How a waiting task is marked", "Which questions a task waits for")
- review B3, M8, M9, M10, m1, m6
- `src/pathly_orchestrator/runner/provenance.py`, `src/pathly_orchestrator/db/queries/comms_tasks.py::claim_task`

## Answer
