# Park a loop task on its question in the scheduler, and give it the answer

Type: task
Status: resolved
Blocked by: 06
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/scheduler.py, src/pathly_orchestrator/supervisor/orchestrator.py, src/pathly_orchestrator/supervisor/orchestrator_stage.py, src/pathly_orchestrator/supervisor/fan_out.py, src/pathly_orchestrator/supervisor/task_wait_outcome.py (new), src/pathly_orchestrator/supervisor/task_prompt.py, tests/dag_goals/test_loop_task_waits.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/dag_goals/INDEX.md

The review's B2. Loop tasks are not executor-owned: under fsm-fan-out Phase E they run inside an
FSM stage (`src/pathly_orchestrator/supervisor/task_prompt.py` docstring), the `execute-task` skill tells the agent not to
complete its task, and the scheduler's completion handler
(`src/pathly_orchestrator/supervisor/scheduler.py`, after the worker returns) calls `complete_task`
on success or `task_retry.resolve_task_failure` on failure. So a loop task whose agent asked a
question is either completed over the open question or retried (`retry_task` sets `pending`,
overwriting a park, and spends an attempt from the scheduler's own `task_attempts` count).

In the completion handler, before the success/failure decision, look up the open questions the
task's spawn posted (`db/queries/task_waits.py::open_questions_by_run` from ticket 06, with the
`sched-<task>#N` run id). If there are any, `park_task` it, do not call `complete_task` or
`resolve_task_failure`, do not count the attempt in `task_attempts` (and where the handler derives `current_attempt` from
the stored `attempts`, subtract `waits`), and broadcast a
`task_waiting` event. The next claim gets a new run id (`attempts` only grows, ticket 06), so the
asking spawn's run id is never reused.

Define the goal-loop run's end with a parked task: `src/pathly_orchestrator/supervisor/fan_out.py` must not read the parked
task as a success, and the run ends (`run_history` status `error`, error `waiting_for_answer`)
instead of `require_tasks_done` blocking it with no way forward; the other ready tasks still
drain first. Put the branch in a new `supervisor/task_wait_outcome.py` and call it from
the handler: `scheduler.py` is at 393 lines.

When a parked loop task is claimed again, `build_task_prompt` adds a short block with each
answered question and its answer (from what ticket 06's `release_waiting_tasks` kept).

## Not in this ticket

- Single runs: tickets 05 and 06. Routing the question to an agent: round two.

## Done when

- `python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider` passes and
  covers: a loop task whose fake agent posts a question and exits successfully is parked, not
  completed; one that exits with a failure and an open question is parked, not retried, and no
  attempt is counted; after an answer it is claimed again with a new `sched-<task>#N` run id and
  its prompt holds the question and answer; a goal-loop run with a parked task ends with
  `waiting_for_answer` after draining the other ready tasks; a loop task with no question behaves as before (complete or retry).
- All existing tests under `tests/dag_goals` and `tests/runner_supervisor` still pass.

```check
$ python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider
exit 0
```

## Reference

- review B2
- `src/pathly_orchestrator/supervisor/task_retry.py`, `src/pathly_data/core/skills/development/execute-task.md`

## Answer

**Built** (work started at 300e23d1; failing test ac2e987c):
- `src/pathly_orchestrator/supervisor/task_wait_outcome.py` (new, 127 lines): `sched_run_id`,
  `park_if_asked` (reads `task_waits.open_questions_by_run` for the spawn's `sched-<task>#N`,
  `park_task`s it, drops the task's `task_attempts`/`task_texts` entries, broadcasts
  `task_waiting` with `task_id`, `run_id`, `questions`), `note_run_waits` / `take_run_waits`
  (the parked tasks recorded on the run), `answered_questions_block`.
- `supervisor/scheduler.py` (393 -> 399): run id from `sched_run_id`; the completion handler
  calls `park_if_asked` before the success/failure branch (on a park neither `complete_task` nor
  `resolve_task_failure`); result key `waiting`.
- `supervisor/fan_out.py`: `_merge_drain_result` reads `waiting` as `outcome: failed` with an
  `error` starting `waiting_for_answer:`; `_drain` calls `note_run_waits`.
- `supervisor/orchestrator_stage.py`: `_resolve_stage_supervised` takes the run's waits after its
  abort check and before `complete_stage`, and `_fail("waiting_for_answer", ...)`s the run.
- `supervisor/task_prompt.py`: `answered_questions_block(task)` after the retry ladder.
- `src/pathly_orchestrator/CLAUDE.md`: "A task waits on its question" gains a Loop tasks
  paragraph; file list lines for `scheduler.py`, `task_wait_outcome.py`, `task_prompt.py`.
- `tests/dag_goals/test_loop_task_waits.py` (new, 6 tests) + `tests/INDEX.md`,
  `tests/dag_goals/INDEX.md`.
- `orchestrator.py` is unchanged (399 lines).

**Proof**:
- `python -m pytest tests/dag_goals/test_loop_task_waits.py -q -p no:cacheprovider`: 6 passed,
  exit 0. At ac2e987c (test only) all 6 failed (task completed over its question, `KeyError:
  'waiting'`, the goal-loop run's asking task `done`). Covered: ask + success -> `blocked`,
  `fail_reason=waiting_for_answer:<qid>`, attempts 1, waits 1, `claimed_by` NULL, a
  `task_waiting` event, no `task_done`; ask + `outcome: failed` with `goal.task_max_attempts=1` ->
  parked, `attempts - waits == 0`, nothing failed or escalated; a question to `architect` ->
  completed; answer -> `pending`, the next claim's run id `sched-<task>#2`, its prompt's
  `## Answers to your questions` holds the question and answer text, then `done` with attempts 2,
  waits 1; no question -> success completes, failure retries `#1`, `#2`, ... and escalates with
  every attempt counted; a real `start_run` of `goal-loop` (in-process FSM, git project, fake
  spawn) with an asking task, an independent task and a dependent of the asking task -> the
  independent one `done`, the asking one `blocked`, the dependent `pending`, only the two task
  spawns (no builder feedback spawn), `state.status == "error"`, `state.error_kind`, the
  `on_done` result `error` both `waiting_for_answer`, `run_history.status == "error"`.
- `python -m pytest tests/dag_goals tests/runner_supervisor -q -p no:cacheprovider`: 623 passed in 136s, exit 0.
- Lint chain (`black --check src/ tests/ && mypy ... && check_file_size.py && check_no_mirror_reads.py
  && gen_test_index.py --check && lint-imports && bandit ...`): exit 0 ("none new, none grown");
  `check_adapters.py` and `check_entry_points.py`: exit 0.

**Decisions**:
- The run's end is decided in `orchestrator_stage._resolve_stage_supervised`, not in
  `orchestrator.py`: `fan_out._drain` records the parked tasks on the run state
  (`note_run_waits`, a private attribute set with `setattr`, so `state.py` is untouched), and the
  stage resolver fails the run before `complete_stage`. `_loop` returns on the resolver's `None`,
  so its own `_fail` never overwrites `error_kind`; `orchestrator.py` needed no change.
- The scheduler does not subtract `waits`: ticket 06's `resolve_task_failure` already does, and on
  the park path the handler calls neither it nor `complete_task`. The parked attempt is dropped
  from `task_attempts` inside `park_if_asked`.
- The park check comes before the success/failure decision, so a question parks the task whatever
  the spawn (or `task_proof`) reported.
- The run id has one source, `sched_run_id`, used by the claim and by `park_if_asked`.
- `answered_questions_block` parses the raw JSON id list and calls
  `db.queries.task_waits.question_answers` (supervisor may not import `http_server`).

**Shortcuts taken**:
- `task_proof.wrap` still proves an attempt that asked a question and reported success (floor
  scan and check blocks run and a `TASK_PROOF` is written) before the handler parks it. It costs
  the check runs only; the next claim is proven again on its own. Worth skipping once proofs get
  expensive.
- The orchestrator still broadcasts its generic `RUNNER_WARNING` ("reported failure ... continuing")
  for the drain's failed outcome just before the stage resolver ends the run.

**For later tickets**:
- 09: a goal-loop run with a parked task ends `error` / `waiting_for_answer`, like a single run;
  the scheduler's drain result has a `waiting` key and broadcasts `task_waiting`.
- The ended run is not resumed by an answer: after the answer the task is `pending` and a new
  goal run (or a chief) has to drain it again.
