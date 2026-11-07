# Close round one's gaps around a parked task

Type: task
Status: resolved
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

Work started at c8521aff247dbaecec56d9dc67397cf72c609a26 (HEAD 83d6aea, a master merge with the same tree).
Test-first commit: f79faf1 (all 7 new tests failed there for the reasons below).

**Built**

- `db/queries/task_waits.py`: `park_and_recheck(conn, task_id, question_ids) -> "parked" | "released" | "not_parked"`
  (`park_task`, then `release_waiting_tasks(ids[0])` when every id is answered now), `task_status`,
  `still_waiting(conn, task_ids)` (parked on a question, or `pending` and not yet run). `park_task`
  keeps its bool (the three consult tests use it). Each SQL is one literal.
- `supervisor/run_task_outcome.py`: `_free_unfinished` parks with `park_and_recheck`.
- `supervisor/task_wait_outcome.py`: `park_if_asked` uses `park_and_recheck`; `not_parked` logs a
  warning naming the task, its `task_status` and the question ids and returns False (handler goes on
  as today); `note_run_waits` keeps only `still_waiting` tasks (fails open to the whole list);
  new `waits_for_answer(result)` (error starts with `waiting_for_answer`).
- `supervisor/task_proof.py`: `_asked(run_id)` (open questions of the run, fail open) returns the
  outcome unproven before `_prove`; the window is still closed by the `finally`.
- `supervisor/orchestrator.py` (now 400 lines): one import line
  (`waits_for_answer as _waits`) and the condition `_outcome_is_failure(invoke_result) and not _waits(invoke_result)`.
- `supervisor/orchestrator_stage.py`: `_record_waiting_outcome(state)` before `_fail(WAITING_FOR_ANSWER)`:
  `_record_run_outcome(storage, state.run_id, "waiting_for_answer")`, storage resolved exactly as
  `registry._record_run_history` does (so the event's feature = `run_history.feature`).
- `tests/dag_goals/test_loop_park_gaps.py` (7 tests), `src/pathly_orchestrator/CLAUDE.md` (file map
  entries, "A task waits on its question", "Task proof in the goal-loop drain"), module docstrings,
  `tests/INDEX.md`, `tests/dag_goals/INDEX.md`.

**Proof**

- `python -m pytest tests/dag_goals/test_loop_park_gaps.py -q -p no:cacheprovider`: `7 passed`, exit 0.
  Covers: single race (settle_run_tasks) -> `pending`, `answered_questions == [qid]`, `waits` 1;
  loop race (drain stopped after the first attempt) -> `pending`, `answered_questions`, `waits` 1,
  `attempts` 1, in `waiting`; a released loop task runs again as `#2` with the answer and
  `note_run_waits` keeps nothing; `park_if_asked` on a `pending` task -> False and a WARNING with the
  task id, `pending` and the question id (caplog); an asking loop attempt that reports success ->
  blocked, no `TASK_PROOF`, the check's marker file never written; a parked goal-loop run -> no
  "continuing to the next stage" RUNNER_WARNING; `GET /runs/<run_id>` -> `outcome: failed`,
  `error: waiting_for_answer`.
- `python -m pytest tests/dag_goals tests/runner_supervisor tests/fsm_flows tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider`:
  `1500 passed, 9 skipped`, exit 0 (includes `tests/runner_supervisor/test_fan_out.py`'s escalated-failure RUNNER_WARNING).
- black --check src/ tests/ clean; mypy "no issues found in 367 source files"; check_file_size OK
  (orchestrator.py 400, task_proof.py 357, others well under); lint-imports 1 kept 0 broken; bandit exit 0;
  check_no_mirror_reads OK; gen_test_index regenerated, `--check` up to date.

**Decisions**

- `park_if_asked` returns True for `released`: the task is `pending` and counts as a wait (no
  attempt spent, entries popped). Returning False would send it to `complete_task` or
  `resolve_task_failure`, i.e. complete it over its question or spend an attempt. The scheduler
  re-reads the frontier each loop, so the released task is claimed again in the same drain
  (`sched-<task>#2`, with `## Answers to your questions`). To keep the run from then ending
  `waiting_for_answer` over a task that ran again (scheduler.py:304 puts it in `result_waiting`,
  and scheduler.py is outside Touches), `note_run_waits` keeps only tasks that still wait
  (`task_waits.still_waiting`). This also fixes the pre-existing case of an answer arriving
  mid-drain. A task freed after the scheduler's last frontier read is `pending` and still counts as
  waiting, so the run ends `waiting_for_answer` as before rather than sending `INCOMPLETE_TASKS` to a builder.
- The single path ignores the `park_and_recheck` result: a released task is `pending` with its
  answers for the next run, and the run still fails `waiting_for_answer` (it stopped to ask).
- Item 4 keys on the stage result's `error` prefix, as the ticket says; the
  `test_fan_out.py` escalated-failure warning has no such prefix and still fires.
- Item 5: `_run_outcome(conn, row["feature"], run_id)` reads `run_history.feature`, which
  `_record_run_history` writes as the storage-dir basename from `Path(state.storage_path)` or
  `_resolve_storage_path(None, project_root, topic)`; `_record_waiting_outcome` resolves the same
  path and `eventlog.append_event` keys by its basename, so the two match (the GET /runs test proves it).

**Shortcuts taken**

- `fan_out._merge_drain_result` still lists a released-and-rerun task in `result.waiting` (and
  sets the `waiting_for_answer` error) for that stage's result, because scheduler.py and fan_out.py
  are outside Touches. Only the stage result is wrong. The run's end and the RUNNER_WARNING read
  `note_run_waits` and the error prefix. One side effect: a drain where one task waited and was
  released while another escalated reports the `waiting_for_answer` error, so the escalation's
  RUNNER_WARNING is not broadcast (`require_tasks_done` still blocks). Ticket 06 changes fan_out.py
  and can drop rerun tasks from `waiting` there.

**For later tickets**

- 06: `park_and_recheck`, `still_waiting` and `task_proof._asked` are the switch points
  (`_asked` reads `open_questions_by_run`; 06 swaps it to `asked_questions_by_run`). Because
  `note_run_waits` already drops tasks that ran again, a released role-question task run in the same
  drain does not end the run `waiting_for_answer`.
- orchestrator.py is at exactly 400 lines: no line may be added there.

