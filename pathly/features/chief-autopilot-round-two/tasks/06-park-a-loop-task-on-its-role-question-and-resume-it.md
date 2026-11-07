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

Work started at f54596839e773196830824569ed6b6b4a504eed8 (test-only commit de8d3db).

**Built**

- `src/pathly_orchestrator/db/queries/task_waits.py`: `asked_questions_by_run(conn, run_id)`, one
  SQL literal: the run's live questions that are in `open_questions_by_run` (called through the
  module global, so the race patches in `test_loop_park_gaps.py` still fire), or addressed to a
  role in `CONSULT_ROLES` (lower/trim, passed as `json_each(?)`, imported inside the function:
  no cycle), or that have a `consult_routes` row; each id once, `ts, id` order. Docstring updated.
- `supervisor/task_wait_outcome.py` (`park_if_asked`) and `supervisor/task_proof.py`
  (`_parked_on_question`) read `asked_questions_by_run`. `run_task_outcome._free_unfinished`
  (single runs, 07) is untouched and still reads `open_questions_by_run`.
- `supervisor/consult_wait.py` (new, 101 lines): `wait_for_consults(task_ids, abort_check,
  timeout)`, `POLL_INTERVAL` (1 s), `CONSULT_SPAWN_TIMEOUT` (600, copied from
  `consult_run._default_spawn`'s literal), `WAIT_TIMEOUT` (690).
- `supervisor/fan_out.py` (373 lines): `_drain` drains, then while the drain has waiting tasks
  and neither abort nor the cost cap: wait for the consults of the still-waiting tasks, and when
  tasks were released drain again with the same tracker and concatenate (`_concat_drains`, ids
  once); then `drained["waiting"]` goes through `still_waiting` (`_still_waiting`) before
  `_merge_drain_result` (HANDOFF 05's carry).
- `tests/dag_goals/test_loop_role_questions.py` (new, 6 tests), `tests/dag_goals/test_loop_task_waits.py`
  (`test_a_question_to_a_role_does_not_park_the_loop_task` now asserts the park: blocked,
  `waiting_for_answer:<qid>`, attempts 1, waits 1, not completed; name kept as the ticket asks).
- `src/pathly_orchestrator/CLAUDE.md` (task_waits/fan_out/consult_wait map lines, "A task waits on
  its question" and "Task proof" paragraphs), `tests/INDEX.md`, `tests/dag_goals/INDEX.md`.

**Proof**

- `python -m pytest tests/dag_goals/test_loop_role_questions.py -q -p no:cacheprovider`: `6 passed`,
  exit 0. Real goal-loop runs with a fake spawn: route `running`, answer posted after the drain's
  wait began -> the wait saw the task `blocked`, released it, spawns `[#1, #2]`, `#2` prompt has
  `## Answers to your questions` with the question and answer, task done, `attempts - waits == 1`,
  `state.status == "done"`; answered before the attempt ended -> rerun `#2` with the answer, done;
  route `running` past a 0.5 s timeout -> waited >= 0.5 s, `error`/`waiting_for_answer`, only `#1`;
  handed to the person (timeout 600) -> every wait < 5 s, `waiting_for_answer`, only `#1`; no
  question -> one spawn, waits 0, done. Plus a unit test of `asked_questions_by_run` (human,
  answered role, handed-on role listed once, "Tester " trimmed; unknown role and other run left out).
- At the test-only commit the same file failed (6 failed: ImportError for `consult_wait` and
  `asked_questions_by_run`) and the flipped test failed (`waiting == [tid]`, got `[]` / completed).
- `python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider`: `6 passed`.
- `python -m pytest tests/dag_goals tests/runner_supervisor tests/fsm_flows tests/comms_board/test_comms_provenance.py -q -p no:cacheprovider`:
  `1511 passed, 9 skipped`, exit 0. `tests/consistency`: 91 passed.
- `black --check src/ tests/` clean; `mypy src/ ...` no issues (368 files); `check_file_size.py`
  OK (none new, none grown); `lint-imports` 1 kept 0 broken; `bandit -q -r src/ -ll -x src/pathly_data/`
  exit 0; `gen_test_index.py` regenerated, `--check` up to date.

**Decisions**

- A question with a `consult_routes` row counts as a role question too: `hand_to_person`
  rewrites `to_agent` to `human`, so a handed-on question the person answered while the attempt
  ran would otherwise be missed. One SELECT over the union dedupes ids that are both open and routed.
- The wait also waits on a route `answered` whose answer row is not posted yet: `consult_run._deliver`
  moves the route to `answered` before it posts the answer, so without this the wait could end in
  that gap and the run stop `waiting_for_answer` on an answer milliseconds away.
- The wait's abort predicate is the FSM abort OR `tracker.exceeded()`; a re-drain that ran nothing
  ends the loop (no spin). A wait read that raises releases nothing (the tasks stay waits).
- `WAIT_TIMEOUT` is 600 + 90 from a constant copied in `consult_wait.py`: consult_run.py is not in
  Touches and holds 600 only as a literal.

**Shortcuts taken**

- `CONSULT_SPAWN_TIMEOUT` duplicates `consult_run._default_spawn`'s `timeout=600`; if that literal
  changes the wait drifts. Worth a shared constant when consult_run.py is next opened (it is at
  398+ lines).
- The wait polls the DB (1 s) instead of being woken by the answer; fine for one drain thread.

**For later tickets**

- 07: `open_questions_by_run` is still the single-run reader; `asked_questions_by_run` is the loop's.
- 09/12: a loop run that waited on consults reports the task once in `completed` (from the second
  drain), and `waiting` only lists still-waiting tasks.
- HANDOFF 05's minor stays: `task_wait_outcome._CARRIED` entries can leak when a drain aborts
  after a wrapper park.

## Review findings (round 1, quality review)

Review: chief-autopilot-round-two 06, quality pass. Range f545968..12dbe0b. END is HEAD, so no later commits were left out. I read the ticket blob at the base commit and did not read the Answer.

Focused tests rerun: tests/dag_goals/test_loop_role_questions.py, test_loop_task_waits.py, test_loop_park_gaps.py, tests/runner_supervisor/test_fan_out.py. 43 passed.

Probe left behind: I ran /tmp/claude-0/-home-user-pathly-adapters/7b5894ea-4de6-51cb-9c61-75dd2332e1f2/scratchpad/probe06q/test_probe06q_selfanswer.py from the scratchpad. Because it sits outside tests/, tests/conftest.py's home isolation did not load, and the run created /root/.pathly/pathly.db and /root/.pathly/global (04:40 UTC). I left them in place. Delete them if they are not wanted.

Inputs probed:
- question to_agent: case, spaces, unknown role, human, *
- the question's author_run_id (stamped from the run token, so an agent cannot charge its question to another task's run)
- answer posts through /comms/answer and through /comms/post type answer
- route status: queued, running, answered with no answer row, to_person, never ends
- the abort flag, goal.max_cost_usd, WAIT_TIMEOUT
- the merge of the two drains, still_waiting

What holds:
- The wait cannot spin. Each loop either releases a task or breaks, and it also breaks when the second drain claims nothing.
- Abort and the cost cap are checked every poll.
- A route that never ends is bounded by WAIT_TIMEOUT for each wait.
- One tracker is passed to both drains, so cost is counted once and the cap applies across the drains.
- claim_task stops a released task from being run twice.
- still_waiting removes tasks that ran again, so the outcome and warning are right.
- A question handed to the person has no pending route, so nothing waits on it and the run ends waiting_for_answer.
- Questions are matched by author_run_id, so another agent cannot park a task on a question that task did not ask.

QUALITY
1. major src/pathly_orchestrator/db/queries/task_waits.py (asked_questions_by_run) with supervisor/task_proof.py / task_wait_outcome.py: a loop task can now re-run forever with no attempt counted. asked_questions_by_run lists role questions that are already answered, and park_and_recheck then releases the task at once (waits+1, attempts-waits unchanged), and scheduler_loop claims it again within the same drain. An agent (or a prompt-injected one) that posts a question to architect and then answers it itself through POST /comms/answer, or a type: answer post with reply_to, which nothing stops a run token from doing, gets a fresh paid spawn every attempt. consult.max_per_task does not stop this: after three routes the question is handed to the person, but the self-answer still marks it answered and still releases the task at once. The attempt limit never fires, because only failures reach resolve_task_failure, and goal.max_cost_usd has no default, so the run is unbounded. Probe: 12 self-answered asks gave 13 spawns of one task in one goal-loop run (status done). At the base commit the same agent got 1 spawn, because an answered question was never in open_questions_by_run. To fix: do not count (or release on) a role question whose only answer was written by the asking run itself (match the answer's author_run_id to the question's), and/or put a ceiling on waits per task. For example, once waits passes consult.max_per_task plus a small margin, keep the task parked for the person instead of releasing it at once. Add a test with a self-answering agent.
2. minor src/pathly_orchestrator/supervisor/consult_wait.py: CONSULT_SPAWN_TIMEOUT = 600.0 copies consult_run._default_spawn's timeout=600 literal instead of sharing a constant, so the two can drift. Also, the 600 s spawn timeout starts only when the spawn host runs the consult. A consult queued behind Studio's headless cap can still be queued or running after 690 s, so the drain gives up early and the run ends waiting_for_answer. When the answer lands later, the task is left pending outside the run. Hoist one constant into consult_run (or a shared module) and import it here. Consider timing from the route's start, or note the limit in the docs.
3. minor src/pathly_orchestrator/supervisor/consult_wait.py: a route that is answered but has no answer row (delivery crashed between set_route_status and the post) is waited on for the full timeout on every loop iteration. Waiting only a short grace period for that state would be enough.
4. minor src/pathly_orchestrator/supervisor/fan_out.py (_concat_drains): if a consult answer frees a task between scheduler_loop's last get_ready_tasks and detect_deadlocks, the task and its dependents are pending and no longer behind a wait, so they are marked deadlocked. They then stay in the first drain's lists while the outer loop has already decided not to drain again. The window is narrow and existed in round one for answers from the person, but the automatic consults make it likelier. To fix, re-check the parked tasks before detect_deadlocks, or skip tasks that were waiting in this drain.

REVIEW: FAIL
