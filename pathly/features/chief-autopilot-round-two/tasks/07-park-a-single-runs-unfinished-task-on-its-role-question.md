# Park a single run's unfinished task on its role question, and tell agents how consults work

Type: task
Status: resolved
Blocked by: 05, 06
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/run_task_outcome.py, src/pathly_data/core/skills/fragments/consult.md, src/pathly_data/core/skills/composition.yaml, src/pathly_data/core/skills/development/drain-dag.md, tests/snapshots/, tests/dag_goals/test_single_role_questions.py (new), tests/dag_goals/test_task_waits_for_answer.py, src/pathly_orchestrator/CLAUDE.md, src/pathly_data/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md, tests/dag_goals/test_loop_park_gaps.py

Delivery for `single` goals, and the agent-facing text for every executor (spec Decisions, "Park
or enrich, per executor"). The drain-dag agent completes its own tasks, so the server can only
hold a task the agent left unfinished.

1. `run_task_outcome._free_unfinished` reads ticket 06's `task_waits.asked_questions_by_run` and
   parks with ticket 05's `park_and_recheck`. The run's error is `waiting_for_answer` when a task
   is still parked, and the new `answer_ready` (a constant beside `WAITING_FOR_ANSWER`) when every
   parked task was released at once because its questions were already answered: the task is
   `pending` with `answered_questions`, no attempt counted, and its next run reads them in the
   ready rows (round one's `tasks_ready.add_answered_questions`). A task the run completed is left
   `done` whatever it asked.
2. `src/pathly_data/core/skills/fragments/consult.md`: questions to a role are answered by a
   consult run Pathly starts, usually within minutes; say what happens per way of running: a loop
   task (`execute-task`) is held and run again with the answer, so finish the attempt on the
   fallback; in `drain-dag`, when the answer decides how to build the task, post the question,
   leave that task unfinished (do not complete or fail it) and go on with the other ready tasks,
   otherwise complete it on the fallback; in a team stage the answer is advice on the board, and a
   needed change is still a `feedback/<TYPE>.md`. Replace "When you are consulted ... answer on the
   board" with: do not answer another agent's question yourself (a consult run does). Keep "never
   block" and the one-bounded-question rule.
3. `src/pathly_data/core/skills/composition.yaml`: add `consult` to `development/execute-task`
   and `development/drain-dag` (before `completion-report`, which stays last), so loop and single
   agents learn they may ask. `src/pathly_data/core/skills/development/drain-dag.md` step 3 says a task whose ready row has
   `answered_questions` uses them (round one), and a task it left for an answer is not claimed
   again in the same run.
4. Regenerate the golden snapshots that compose `consult` (`tests/snapshots/team__build.claude.md`,
   `team__review`, `team__test`; round one learnings 03 gives the recipe).
5. `tests/dag_goals/test_task_waits_for_answer.py` asserts round one's "a question to a role
   (`to: architect`) does not park the task": change that test in place to assert the park (keep
   the test function).

## Not in this ticket

- Starting the single goal again after `answer_ready` or an answer: the person or the chief
  (restarting an ended run is round four).
- Loop tasks: ticket 06.

## Done when

- `python -m pytest tests/dag_goals/test_single_role_questions.py -q -p no:cacheprovider` passes
  and covers: a single run whose agent asked `architect` and left its task `in_progress` parks it
  (`blocked`, `waiting_for_answer:<id>`) and the run fails `waiting_for_answer`; with the answer
  already posted when the run ends, the task is `pending` with `answered_questions`, `waits` 1, and
  the run's error is `answer_ready` (in `GET /runs/<id>`); a role answer posted later frees the
  parked task and its ready row carries the question and answer; a task the agent completed after
  asking stays `done`.
- `python -m pytest tests/dag_goals/test_task_waits_for_answer.py tests/install_skills -q -p no:cacheprovider`
  passes, with the role-question test asserting a park and the regenerated snapshots matching.
- All existing tests under `tests/dag_goals` and `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/dag_goals/test_single_role_questions.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals/test_task_waits_for_answer.py tests/install_skills -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- spec.md § Decisions ("Park or enrich, per executor"), § Edge cases
- round one `pathly/features/chief-autopilot/tasks/06-park-a-task-on-its-question.md` (Answer)
- `src/pathly_data/core/skills/development/execute-task.md` (read-only)

## Answer

**Built**

- `src/pathly_orchestrator/supervisor/run_task_outcome.py`: `ANSWER_READY = "answer_ready"` beside
  `WAITING_FOR_ANSWER`; `_free_unfinished` reads `task_waits.asked_questions_by_run` (open human/`*`
  questions plus every role or routed question, answered or not, minus self-answered) and maps
  `park_and_recheck`'s results: any `parked` -> `waiting_for_answer` (count of parked tasks), else
  any `released` -> `answer_ready` (count released), else `(None, 0)`. Module and
  `free_tasks_of_failed_spawn` docstrings updated. 234 lines.
- `src/pathly_data/core/skills/fragments/consult.md`: role questions are answered by a consult run
  Pathly starts, usually within minutes; per way of running: loop task held and run again (finish on
  the fallback), `drain-dag` leaves the task unfinished and goes on when the answer decides how to
  build it (else completes on the fallback), team stage = advice on the board, a needed change is a
  `feedback/<TYPE>.md`. "When you are consulted ... answer on the board" replaced with "do not answer
  another agent's question yourself ... a consult run does". "Never block", the one-bounded-question
  rule and the run-token line are kept.
- `src/pathly_data/core/skills/composition.yaml`: `consult` added to `development/execute-task` and
  `development/drain-dag`, before `completion-report` (still last).
- `src/pathly_data/core/skills/development/drain-dag.md` step 3: `answered_questions` may come from
  the person or a role; a task left unfinished for an answer is not claimed again in this run.
- `tests/snapshots/team__build.claude.md`, `team__review.claude.md`, `team__test.claude.md`
  regenerated with `compose_skill(skill, "claude")` (only these three snapshots differed).
- `tests/dag_goals/test_single_role_questions.py` (new, 4 tests); `tests/dag_goals/test_task_waits_for_answer.py`:
  `test_a_question_to_a_role_does_not_park` now asserts the park (function kept);
  `tests/dag_goals/test_loop_park_gaps.py`: ticket 05's single-race test now expects
  `answer_ready` (Touches widened in 7953af3).
- `src/pathly_orchestrator/CLAUDE.md` (task_waits and run_task_outcome entries, "A task waits on its
  question"), `src/pathly_data/CLAUDE.md` (drain-dag / execute-task fragment lists),
  `tests/INDEX.md`, `tests/dag_goals/INDEX.md`.

**Proof**

- Test first: the test-only commit failed for the right reasons (`'task_unfinished' == 'waiting_for_answer'`,
  `'task_unfinished' == 'answer_ready'`, `'pending' == 'blocked'`).
- `python -m pytest tests/dag_goals/test_single_role_questions.py -q -p no:cacheprovider`: 4 passed, exit 0 (covers the park + `waiting_for_answer`, the at-once release + `answer_ready` in `GET /runs/<id>`, a later role answer freeing the task with question and answer in its ready row, a completed task staying `done`).
- `python -m pytest tests/dag_goals/test_task_waits_for_answer.py tests/install_skills -q -p no:cacheprovider`: 430 passed, 2 skipped, exit 0 (the flipped role-question test asserts the park; `test_team_skill_matches_golden_snapshot` passes on the regenerated snapshots).
- `python -m pytest tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider`: 699 passed, exit 0.
- Full `python -m pytest tests/ -q -p no:cacheprovider`: 6778 passed, 14 skipped, exit 0. An earlier full run, made while two other pytest runs were going at the same time, failed once in ticket 06's timing test `test_loop_role_questions.py::test_the_drain_waits_for_the_consult_and_runs_the_task_again_with_the_answer` (the wait released nothing). That loop path is untouched here; the test passed 3 of 3 times on its own and in the clean full run.
- `python3 scripts/check_file_size.py` OK (none new, none grown); `python scripts/gen_test_index.py --check`
  up to date; `black --check src/ tests/` clean.

**Decisions**

- A mix of parked and released tasks reports `waiting_for_answer` (the run still waits on
  something); `answer_ready` only when no task stays parked and at least one was released.
- A run none of whose tasks could be parked (no longer `in_progress`, a race) returns no error, as
  for a run that left no task.
- Single runs pass no `hold_over` to `park_and_recheck`: the next single run is started by the person
  or the chief, never automatically, so no wait ceiling is needed there.
- Ticket 05's single race case (an answer between the read and the park) is `answer_ready` now, per
  this ticket's item 1 and the spec's Edge cases row.

**Shortcuts taken**

- `free_tasks_of_failed_spawn` still ignores the returned error (it only logs it), so a spawn that
  raised writes no `answer_ready`; its `run_history` already says `error`. Worth upgrading if the
  chief must tell `answer_ready` from a crash for failed spawns.
- No wait ceiling for single runs (see Decisions): an agent that answers its own question through
  `/comms/answer` (no `author_run_id`) gets a free re-run on each manual restart.

**For later tickets**

- 09/12: a single run's `GET /runs/<id>` error may now be `answer_ready` (task `pending` with its
  answers, ready to start again) besides `waiting_for_answer`; notices should treat it as "can be
  started again", not as waiting.
- Loop and single agents now compose `consult`, so `development/execute-task` and
  `development/drain-dag` prompts are longer; no golden snapshot exists for them.

## Attempt note

Closed: attempt 2 finished the ticket after Touches was widened (7953af3); see the Answer.

Attempt 1 (started at c9a97fc, branch HEAD da5180f; test-first commit 2c70d31). Everything in
the ticket is built and its own Done-when checks pass, but one existing test outside `Touches`
now fails, so the ticket is left open: the plan has to change, not the footprint.

- Fails: `tests/dag_goals/test_loop_park_gaps.py::test_single_an_answer_between_the_read_and_the_park_leaves_the_task_pending`
  (ticket 05's single-run race test) asserts `error == "waiting_for_answer"` for a single run
  whose parked task an answer released at once (the answer lands between the question read and
  the park). Item 1 of this ticket and the spec's Edge cases row ("A single run whose parked task
  was released before the run settled | run error `answer_ready`") make that exact case
  `answer_ready`, which is what `settle_run_tasks` now returns
  (`AssertionError: assert 'answer_ready' == 'waiting_for_answer'`). Its other asserts (task
  `pending`, reason cleared, `answered_questions == [qid]`, `waits` 1) still hold.
- Needed: add `tests/dag_goals/test_loop_park_gaps.py` to this ticket's `Touches` and change
  that one assert to `"answer_ready"` (ticket 05's Answer says "The single path ignores the
  `park_and_recheck` result ... the run still fails `waiting_for_answer`", which this ticket
  deliberately reverses). No other change is needed.
- Built so far (committed with this note): `supervisor/run_task_outcome.py` (`ANSWER_READY`;
  `_free_unfinished` reads `asked_questions_by_run` and maps `park_and_recheck`'s results: any
  `parked` -> `waiting_for_answer`, else any `released` -> `answer_ready`, else `(None, 0)`),
  `fragments/consult.md`, `composition.yaml` (`consult` before `completion-report` in
  `development/execute-task` and `development/drain-dag`), `development/drain-dag.md` step 3,
  the three regenerated team snapshots, the flipped role-question test, the new
  `tests/dag_goals/test_single_role_questions.py` (4 tests), both CLAUDE.md files and the
  INDEX files.
- Measured: `tests/dag_goals/test_single_role_questions.py` 4 passed;
  `tests/dag_goals/test_task_waits_for_answer.py tests/install_skills` 430 passed, 2 skipped;
  `tests/dag_goals tests/runner_supervisor` 1 failed (the test above), 698 passed;
  `tests/consistency` 91 passed; `check_file_size.py` OK; `gen_test_index.py --check` up to date;
  `black --check src/ tests/` clean.
