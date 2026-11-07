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
  are outside Touches. Only the stage result is wrong. The run's end reads `note_run_waits`, and
  (since review round 1) the RUNNER_WARNING reads `waits_for_answer`, which also asks
  `still_waiting`, so a real escalation is warned about (see Review fixes, major 2).

**For later tickets**

- 06: `park_and_recheck`, `still_waiting` and `task_proof._asked` are the switch points
  (`_asked` reads `open_questions_by_run`; 06 swaps it to `asked_questions_by_run`). Because
  `note_run_waits` already drops tasks that ran again, a released role-question task run in the same
  drain does not end the run `waiting_for_answer`.
- orchestrator.py is at exactly 400 lines: no line may be added there.


**Review round 1 (send-back)**

Work restarted at e23091a. Test-first commit: 7907010 (5 new tests, all failing for the reasons
below). Reproduced first with the reviewer's probe: (a) `completed=[tid]`, no TASK_PROOF, check not
run; (b) `completed=[tid]`, one spawn, no proof; major 2 `waits_for_answer` True.

*Built:* `supervisor/task_proof.py` (`_asked` replaced by `_parked_on_question`: reads the run's
open questions and parks with `park_and_recheck` in the wrapper, while the attempt can still be
proven; `parked`/`released` -> `task_wait_outcome.carry_park(run_id, ids, result)` and the outcome
is returned unproven; `not_parked` or any read/park error -> the attempt is proven as before);
`supervisor/task_wait_outcome.py` (`carry_park` / `_take_carried`, a lock-guarded run_id dict;
`park_if_asked` takes a carried park as it is, with no second read; `waits_for_answer` also
requires `still_waiting` to find one of `result["result"]["waiting"]`, fail open to the error
word); `db/queries/task_waits.py` (`park_and_recheck` never raises once the park is committed;
reports `released` from the task's status after the recheck); `src/pathly_orchestrator/CLAUDE.md`
("A task waits on its question", "Task proof in the goal-loop drain", file map);
`tests/dag_goals/test_loop_park_gaps.py` (+5 tests); `tests/dag_goals/INDEX.md`.

*Proof:* `python -m pytest tests/dag_goals/test_loop_park_gaps.py -q -p no:cacheprovider`: `12 passed`,
exit 0. `python -m pytest tests/dag_goals tests/runner_supervisor tests/fsm_flows tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider`:
`1505 passed, 9 skipped`, exit 0. black --check: 747 unchanged; `mypy src/ --ignore-missing-imports --no-strict-optional`:
no issues in 367 files; check_file_size OK (task_proof.py 379, task_wait_outcome.py 206, task_waits.py 256,
orchestrator.py 400, unchanged); check_no_mirror_reads OK; lint-imports 1 kept 0 broken; bandit exit 0;
gen_test_index regenerated, `--check` up to date. The reviewer's probe now gives (a) `completed=[]`,
`failed=[tid]`, a TASK_PROOF with `checks: failed`, and major 2 `waits_for_answer` False; its (b)
patches `task_proof._asked`, which no longer exists, so `test_an_answer_between_the_proof_read_and_the_park_releases_the_task` covers it.

*Review fixes*

1. Major 1 (fixed). The wrapper parks the asking attempt itself and carries the ids to the
   handler, so there is one read: an answer that lands after it is caught by
   `park_and_recheck`'s recheck (released at once, a wait, `#2` runs with the answer and is proven).
   Releasing in the worker thread is safe: the task's lane stays in `in_flight_lanes` until the
   handler runs, so the frontier cannot claim it early. A task that cannot be parked (the agent
   marked it done itself, or the read/park raised) is proven in the wrapper; the handler then
   sees `not_parked` (warning) and goes on with the proven outcome, so a failing check goes to
   `resolve_task_failure`. Tests: `test_an_asking_attempt_that_marked_its_own_task_done_is_proven`
   (failed, not completed, check ran, TASK_PROOF written) and
   `test_an_answer_between_the_proof_read_and_the_park_releases_the_task` (spawns `#1`, `#2`, the
   answer in `#2`'s prompt, completed, TASK_PROOF only for `#2`, waits 1).
2. Major 2 (fixed inside Touches). `waits_for_answer` is True only when `still_waiting` finds a
   `waiting` task that still waits, so orchestrator.py's RUNNER_WARNING fires for a released task
   that ran again and escalated; orchestrator.py is unchanged (400 lines). Test:
   `test_a_drain_whose_waiting_task_ran_again_and_failed_is_not_a_wait`. Left as is: the stage
   result's `error` from `fan_out._merge_drain_result` still says `waiting_for_answer: N task(s)
   wait ...` in that case (and `outcome`/`result.waiting` still list the task). **Ticket 06 must
   filter `drained["waiting"]` through `task_waits.still_waiting` in `fan_out._drain`** before
   `_merge_drain_result`, so the error, outcome, `note_run_waits` and the warning read one list.
3. Minor 3 (fixed). `park_and_recheck` catches errors after the park commit and returns `parked`,
   so the handler counts a wait and never runs `complete_task` on a blocked task. Test:
   `test_park_and_recheck_reports_a_park_whose_recheck_fails`.
4. Minor 4 (fixed). `released` is read from the task's status after the recheck, so a release the
   answer's own `release_on_answer` won is reported as `released`. Test:
   `test_park_and_recheck_reports_a_release_the_answer_won`.
5. Minor 5 (not fixed, answered). A `pending` released task counts as waiting so that one freed
   after the scheduler's last frontier read ends the run `waiting_for_answer` rather than sending
   `INCOMPLETE_TASKS` to a builder. An `abort_check` from the FSM's own abort is caught by
   `_resolve_stage_supervised`'s abort check before `take_run_waits` (the run ends `aborted`), so
   only a cost-cap stop after a release reports `waiting_for_answer`. Telling those apart needs the
   drain's abort reason, which `note_run_waits` is not given (fan_out.py, outside Touches); 06 can
   pass it when it changes `_drain`.
6. Minor 6 (not fixed, answered). With major 2 fixed, a wait plus an escalation in one drain still
   ends the run `waiting_for_answer` (the run's end comes first, as the spec words it); the stage
   error naming both lives in `fan_out._merge_drain_result` (outside Touches, owned by 06). The
   RUN_OUTCOME error stays the bare `waiting_for_answer` the ticket's Done when asks for.

*Shortcuts:* the carried-park dict keeps an entry if a drain stops before handling that
completion (one small tuple per lost completion, cleared on process exit); worth a sweep only if
drains are aborted mid-flight often.

*For later tickets:* 06 swaps `open_questions_by_run` to `asked_questions_by_run` in
`task_proof._parked_on_question` (was `_asked`) and in `park_if_asked`'s fallback read; the filter
in `fan_out._drain` is above. `tests/dag_goals/test_loop_park_gaps.py` is 559 lines: the 400-line
rule (`check_file_size.py`) covers `src/` only, and no second test file is in this ticket's
Touches, so it was not split.

## Review findings (round 1, quality review)

Ticket 05 (chief-autopilot-round-two), quality pass. Range c8521af..4b299a1 (END = HEAD, so no later commits were left out). The ticket was read at c8521af, and its Answer was not read. The focused tests pass (51 passed), and check_file_size is OK (orchestrator.py is at exactly 400 lines). I left a probe test in the scratchpad (/tmp/claude-0/-home-user-pathly-adapters/7b5894ea-4de6-51cb-9c61-75dd2332e1f2/scratchpad/probe/test_probe_05q.py). It is outside the repo, and nothing in the repo changed.

Inputs probed: the timing of the answer post (between each read and the write that follows), the task's status at park time (the agent can set it through POST /comms/tasks/status with its own run token), the drain's waiting list as the scheduler returns it, the stage result's error string, and the RUN_OUTCOME storage path.

QUALITY
1. major src/pathly_orchestrator/supervisor/task_proof.py: an asking attempt is no longer proven, but the task can still be completed. wrap() skips _prove whenever _asked(run_id) is true. The scheduler then completes the task with no proof whenever park_if_asked returns False. I reproduced this two ways, each with a task whose check block exits 1: (a) the agent posts a question to human, marks its own task done (POST /comms/tasks/status, which is allowed for its own board), and reports success. park_task finds no in_progress row, so the result is not_parked, then a warning, then complete_task. The result is completed=[tid], no TASK_PROOF, and the check never ran. (b) An answer lands after _asked and before park_if_asked's open_questions_by_run. That read finds no open question, so the handler completes the task, again with no proof and no check. At c8521af the proof always ran. The goal-loop's DRAINING->DONE task_checks and floor_gate still run these checks later, but by then the task is done and its dependents have run on top of unproven work. Fix: carry the asked question ids from wrap to the handler (for example a marker on the outcome) and park with those ids. park_and_recheck then releases at once if they are already answered. Never let an attempt that was left unproven because it asked reach complete_task: if it cannot be parked, prove it then or route it to resolve_task_failure.
2. major src/pathly_orchestrator/supervisor/scheduler.py + fan_out.py (from task_wait_outcome.note_run_waits / park_and_recheck): a task freed by park_and_recheck stays in the scheduler's result_waiting. Only note_run_waits filters it, through still_waiting, and _merge_drain_result does not. Suppose the freed task runs again in the same drain and escalates (or completes). The merged stage result still says outcome failed and error "waiting_for_answer: 1 task(s) wait...". take_run_waits returns [], so the run goes on to complete_stage. waits_for_answer(result) is true, so orchestrator.py drops the RUNNER_WARNING for a real escalation. I confirmed this: _merge_drain_result({failed:[t1], waiting:[t1]}) gives a waiting_for_answer error, and waits_for_answer returns True. That is a failure with nothing waiting that raises no warning and is reported as a wait. Fix: in fan_out._drain, filter drained["waiting"] through still_waiting before _merge_drain_result, so outcome, error, note_run_waits and the warning all read the same list. Or the scheduler can drop a task from result_waiting when it is claimed again.
3. minor src/pathly_orchestrator/supervisor/task_wait_outcome.py: park_and_recheck commits the park before release_waiting_tasks runs. If the recheck raises (for example, the database is locked), park_if_asked catches the error and returns False. The handler then runs complete_task, which does not check the task's status, on a task that is now blocked. Fix: return True (it waits) once the park has committed, even if the recheck fails, or catch errors inside park_and_recheck after the park.
4. minor src/pathly_orchestrator/db/queries/task_waits.py: if the answer's own release_on_answer frees the task first, park_and_recheck returns "parked" for a task that is already pending. The task state is still correct; only the log line ("... (parked)") is wrong.
5. minor src/pathly_orchestrator/supervisor/task_wait_outcome.py: still_waiting counts any pending task as waiting. If the drain is aborted after a release, the run ends with waiting_for_answer and RUN_OUTCOME waiting_for_answer, even though nothing is open for a person.
6. minor src/pathly_orchestrator/supervisor/orchestrator.py: when a true wait and a non-wait escalation happen in the same drain, the error says only waiting_for_answer, and the escalation gets no warning. This matches the spec's wording, but it should be named in the RUN_OUTCOME or notice text.

REVIEW: FAIL
