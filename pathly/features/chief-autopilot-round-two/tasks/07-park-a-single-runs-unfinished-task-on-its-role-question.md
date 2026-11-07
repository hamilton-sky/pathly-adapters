# Park a single run's unfinished task on its role question, and tell agents how consults work

Type: task
Status: open
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

## Attempt note

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
