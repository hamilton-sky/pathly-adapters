# Park a single run's task on its open question, and free it on any answer

Type: task
Status: resolved
Blocked by: 05
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/run_task_outcome.py, src/pathly_orchestrator/db/queries/comms_tasks_by_run.py, src/pathly_orchestrator/db/queries/task_waits.py (new), src/pathly_orchestrator/db/migrations_task_waits.py (new), src/pathly_orchestrator/db/migrations_incremental.py, src/pathly_orchestrator/db/queries/comms_messages.py, src/pathly_orchestrator/supervisor/task_retry.py, src/pathly_orchestrator/http_server/blueprints/comms/tasks_ready.py (new), src/pathly_orchestrator/http_server/blueprints/comms/tasks.py, src/pathly_data/core/skills/development/drain-dag.md, tests/snapshots/, tests/dag_goals/test_task_waits_for_answer.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

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
  `src/pathly_orchestrator/db/migrations_task_waits.py` (new), wired through
  `src/pathly_orchestrator/db/migrations_incremental.py` the way `migrations_chief` is; `src/pathly_orchestrator/db/migrations.py` is at its
  baseline). `attempts` is left alone:
  the loop scheduler builds its spawn's run id from it (`sched-<task>#<attempts+1>`), so it must
  only grow. Every attempt-limit check (`task_retry.resolve_task_failure`, ticket 05's limit)
  compares `attempts - waits` with the limit, so waiting never spends a retry. In the loop
  scheduler that is where it works out `current_attempt` from the stored `attempts` (ticket 12).
  `release_waiting_tasks` clears the `waiting_for_answer` reason when it frees a task, so
  `task_retry.build_retry_context` never shows the wait as "the previous attempt failed".
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

**Built** (work started at 1339379e; failing test 5c068e06):
- `src/pathly_orchestrator/db/queries/task_waits.py` (new): `open_questions_by_run`, `park_task`,
  `release_waiting_tasks` (+ best-effort `release_on_answer`), `waiting_question_ids`,
  `task_waits`, `tasks_behind_waiting`, `question_answers`. Every SQL one literal.
- `src/pathly_orchestrator/db/migrations_task_waits.py` (new): `add_task_waits` adds
  `comms_messages.waits INTEGER NOT NULL DEFAULT 0` and `answered_questions TEXT`; wired last in
  `db/migrations_incremental.py`.
- `db/queries/comms_messages.py::post_message`: after the write lock, `type == "answer"` with
  `reply_to` calls `release_on_answer` (389 -> 392 lines). Covers `/comms/answer`
  (`answer_question` posts through `post_message`) and `/comms/post`.
- `db/queries/comms_tasks_by_run.py`: the unfinished-task read returns `waits`.
- `supervisor/run_task_outcome.py`: `_free_unfinished` parks the run's `in_progress` tasks on
  its open questions (error `waiting_for_answer`) before the unfinished check, else frees them
  (`task_unfinished`); used by `settle_run_tasks` and `free_tasks_of_failed_spawn`.
  `counted_attempts` = `attempts - waits`.
- `supervisor/task_retry.py`: `resolve_task_failure` compares `current_attempt - waits` (read
  from the DB) with the limit; `detect_deadlocks` skips tasks behind a parked task.
- `http_server/blueprints/comms/tasks_ready.py` (new) + `tasks.py`: every `GET /comms/tasks` row
  carries `answered_questions: [{question, answer}]` (`[]` when it never waited).
- `src/pathly_data/core/skills/development/drain-dag.md`: step 3 tells the agent to read
  `answered_questions` first. No snapshot composes drain-dag (none regenerated).
- `src/pathly_orchestrator/CLAUDE.md`: route lines, file list, the 05 section's
  `counted_attempts`, new section "A task waits on its question".
- `tests/dag_goals/test_task_waits_for_answer.py` (new, 11 tests) + INDEX files.

**Proof**:
- `python -m pytest tests/dag_goals/test_task_waits_for_answer.py -q -p no:cacheprovider`:
  11 passed, exit 0. At 5c068e06 (test only) all 11 failed (`no such column: waits`). Covered:
  run that asked and left its task `in_progress` -> task `blocked`,
  `fail_reason='waiting_for_answer:<qid>'`, attempts 1, waits 1, result and `GET /runs/<id>`
  failed with `waiting_for_answer`, status error; three park-and-answer cycles with
  `goal.task_max_attempts=2` then an unfinished fourth run -> `attempts - waits == 1`, task
  `pending`, no escalation; `resolve_task_failure(current_attempt=4)` with waits 3 and limit 2
  -> `retried`; a question to `architect` -> `task_unfinished`, waits 0; `/comms/answer` and a
  `type: answer` post with `reply_to` both free the task; two questions (`human` and `*`) -> blocked
  after the first answer, pending after the second; child and grandchild of the parked task not
  deadlocked; ready row carries `[{question, answer}]`; answer after the task was deleted is
  stored, task row unchanged, no error; open question with the task `done` keeps success.
- `python -m pytest tests/dag_goals tests/comms_board tests/install_skills -q -p no:cacheprovider`:
  2141 passed, 2 skipped, exit 0.
- Lint chain: exit 0 (black, mypy, check_file_size "none new, none grown", mirror reads, INDEX
  check, lint-imports 1 kept, bandit, adapters, entry points). `tests/consistency`: 89 passed.
- Extra: `tests/db tests/runner_supervisor tests/http_api`: 3105 passed, 2 skipped, exit 0.

**Decisions**:
- The answered ids live in a new JSON column `answered_questions` (the ticket allowed "reason or
  a JSON field"): keeping them in `fail_reason` would make `build_retry_context` show them as a
  failed attempt. The release sets `fail_reason` NULL.
- One release hook in `post_message` (after its lock, best-effort) covers both answer paths, so
  `answer_question` needs no second call (it posts through `post_message`, and the answer row is
  what `_is_answered` checks; the status update comes after).
- `park_task` only parks an `in_progress` task and clears `claimed_by`, like `retry_task`.
- A crashed spawn (`free_tasks_of_failed_spawn`) with an open question parks its task too: freeing
  it would re-run it without the answer.
- `resolve_task_failure` reads `waits` itself, so the loop path is covered without touching
  `scheduler.py` (ticket 12).
- `answered_questions` is decorated on every `GET /comms/tasks` row (both branches share the
  loop), so no row ever returns the raw JSON string.

**Shortcuts taken**:
- `release_waiting_tasks` finds candidates with `instr(fail_reason, ?)` and confirms by parsing;
  fine for a board's task count, not indexed.
- `tasks_behind_waiting` loads the board/scope's tasks once per `detect_deadlocks` call; fine for
  a DAG of tens of tasks.

**For later tickets**:
- 12: use `task_waits.park_task` / `open_questions_by_run`; `resolve_task_failure` already
  subtracts `waits`, so the scheduler's `current_attempt` can stay `attempts`-based; a parked loop
  task's `claimed_by` is NULL after `park_task`.
