# Fail a single run that leaves its task unfinished, and free the task

Type: task
Status: open
Blocked by: 11
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/terminal_reconcile.py, src/pathly_orchestrator/supervisor/terminal.py, src/pathly_orchestrator/supervisor/terminal_identity.py, src/pathly_orchestrator/supervisor/run_task_outcome.py (new), src/pathly_orchestrator/db/queries/comms_tasks_by_run.py (new), src/pathly_orchestrator/db/queries/run_history_read.py, tests/runner_supervisor/test_unfinished_task_outcome.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

Spike S6: a goal run with the default `single` executor ended `done` with a synthetic
`AGENT_DONE` `outcome: "success"` while the task it claimed stayed `in_progress`.
`src/pathly_orchestrator/supervisor/terminal_reconcile.py::_synthesize_agent_done_if_missing`
hard-codes `"outcome": "success"`. A board or single run has no per-task retry
(`task_retry.resolve_task_failure` is called only by the loop scheduler), and `claim_task` needs
`pending`, so the task can never be claimed again.

After ticket 11, `claimed_by` is the run id. At the end of an executor-owned board or single run
(`terminal_reconcile`, where `executor_owned_telemetry` is set), look up the tasks still
`in_progress` with `claimed_by` this run (new read query in
`src/pathly_orchestrator/db/queries/comms_tasks_by_run.py` (new); `comms_tasks.py` is at 418 lines,
ratchet baseline, do not grow it). Put the decision in
`src/pathly_orchestrator/supervisor/run_task_outcome.py` (new). If there is at least one such task and
no open question (ticket 06 adds that case):

- the synthetic `AGENT_DONE` (written when the agent wrote none) carries `"outcome": "failed"`
  and `"error": "task_unfinished"`. When the agent wrote its own `AGENT_DONE` saying `success`, do
  NOT write a second `AGENT_DONE`: the invocation projection writes one row per `AGENT_DONE` and
  billing folds onto the newest, so a second one double-counts the run
  (`src/pathly_orchestrator/db/queries/invocation_projection.py`). Instead append a `RUN_OUTCOME` event
  `{run_id, outcome: "failed", error}` that the projection ignores, and make the run read behind
  `GET /runs/<id>` (`src/pathly_orchestrator/db/queries/run_history_read.py`) report the latest `RUN_OUTCOME` over the
  `AGENT_DONE`'s outcome;
- the run's `run_history` status is `error` (through the path that writes its terminal status,
  `supervisor/registry.py::_record_run_history` or the board run's own);
- each such task goes back to `pending` with `fail_reason='task_unfinished'`, counting the attempt
  the claim already took; past `goal.task_max_attempts`
  (`task_retry.resolve_max_attempts`, compared with `attempts - waits`, see ticket 06), it is failed the way `task_retry.fail_task` fails a loop
  task (its dependents blocked, an escalation posted).

A run whose tasks are all `done` is unchanged. Loop tasks are not touched here: the scheduler owns
them (ticket 12).

## Not in this ticket

- Questions: ticket 06.
- Loop tasks: ticket 12. Flow (FSM) runs: their gates already judge tasks.

## Done when

- `python -m pytest tests/runner_supervisor/test_unfinished_task_outcome.py -q -p no:cacheprovider`
  passes and covers, with drain-dag's literal claim body: a single run that ends with its task
  `in_progress` and no `AGENT_DONE` is failed with `task_unfinished`; the same with the agent's own
  `success` is reported failed in `GET /runs/<id>` and the run still has exactly one
  `agent_invocations` row; the task is `pending` and the next goal start
  claims it; at the attempt limit it is failed and an escalation is posted; a run whose task is
  `done` keeps `success`.
- All existing tests under `tests/runner_supervisor` and `tests/dag_goals` still pass.

```check
$ python -m pytest tests/runner_supervisor/test_unfinished_task_outcome.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor tests/dag_goals -q -p no:cacheprovider
exit 0
```

## Reference

- spike19-part-b-report.md § 5, review B1, M11, m2
- `src/pathly_orchestrator/supervisor/task_retry.py`, `src/pathly_orchestrator/supervisor/board_run.py::start_board_run`

## Answer

**Built** (work started at daa6b1c0; failing test a5a79e5f):
- `src/pathly_orchestrator/db/queries/comms_tasks_by_run.py` (new): `get_unfinished_tasks_of_run(conn, run_id)`, the tasks still `in_progress` with `claimed_by` = the run (one SQL literal).
- `src/pathly_orchestrator/supervisor/run_task_outcome.py` (new): `settle_run_tasks(state, run_id, storage, own_agent_done)` frees each such task (`task_retry.retry_task` with `task_unfinished` while `counted_attempts` < `resolve_max_attempts()`, else `fail_task` + `task_retry._post_escalation`), marks the run failed for `take_run_failure`, and appends a `RUN_OUTCOME {run_id, outcome: failed, error}` when the agent's own `AGENT_DONE` does not already say failed. Returns `task_unfinished` or None. Skips non-executor-owned runs, the `goal-loop` flow and `sched-` run ids.
- `supervisor/terminal_reconcile.py::_synthesize_agent_done_if_missing`: calls `settle_run_tasks` first (passing the agent's own AGENT_DONE when it exists); the synthetic event carries `outcome: failed` + `error: task_unfinished` when it returned an error.
- `supervisor/terminal.py`: the early-advance path (agent's own AGENT_DONE won) calls `settle_run_tasks` (+2 lines, 394 -> 396).
- `supervisor/terminal_identity.py::_settle_spawn_identity`: status `error` when `take_run_failure(run_id)` is true.
- `db/queries/run_history_read.py`: `_run_outcome` adds `run.outcome` / `run.error` to `GET /runs/<id>`: latest `RUN_OUTCOME` for the run over its latest `AGENT_DONE` (no outcome field -> success, no event -> null). 389 lines.
- `src/pathly_orchestrator/CLAUDE.md`: two file-list lines and a section "No success over an unfinished task".
- `tests/runner_supervisor/test_unfinished_task_outcome.py` (new, 6 tests) + `tests/INDEX.md`, `tests/runner_supervisor/INDEX.md`.

**Proof**:
- `python -m pytest tests/runner_supervisor/test_unfinished_task_outcome.py -q -p no:cacheprovider`: 6 passed, exit 0. Each test drives the real `_run_stage_via_terminal` for a `board-run` state; the agent claims through `POST /comms/tasks/claim` with drain-dag's literal body `{"run_id": "$GOAL_ID-single"}` and the spawn's run token. Covered: no AGENT_DONE + task in_progress -> synthetic AGENT_DONE `failed`/`task_unfinished`, run_history `error`, task `pending`, `fail_reason='task_unfinished'`, attempts 1; agent's own `success` (PTY-first and early-advance) -> `GET /runs/<id>` outcome failed, status error, exactly one `agent_invocations` row, own AGENT_DONE still the last; the freed task is claimed by the next run (claimed_by = new run, attempts 2), which finishes it and keeps success; with `goal.task_max_attempts=2` the second unfinished run fails the task, blocks its dependent and posts one escalation naming `task_unfinished`; a run whose task is `done` keeps `success` / `done`.
  At a5a79e5f (test only, checked in a separate worktree) all 6 failed: outcome `success`, no `outcome` key in the run detail, task left `in_progress`.
- `python -m pytest tests/runner_supervisor tests/dag_goals -q -p no:cacheprovider`: 604 passed, exit 0.
- Lint chain from commands.md: exit 0 (black, mypy, check_file_size "none new, none grown", mirror reads, INDEX check, lint-imports, bandit, adapters, entry points).
- Extra: `tests/db tests/comms_board`: 1646 passed, 2 skipped; `tests/http_api -k "runs or run_detail or control"`: 170 passed.

**Decisions**:
- The run_history `error` is carried to `_settle_spawn_identity` through a small in-process set in `run_task_outcome` (`take_run_failure` pops it), so `RunnerState` (state.py, not in Touches) gets no new field and terminal.py's finally is unchanged.
- One hook point per path: the PTY-first and slow paths already call the synthesizer, so the decision lives inside it; only the early-advance path needed a new call.
- `RUN_OUTCOME` is written only when the agent's own AGENT_DONE does not already say `failed`.
- `_run_outcome` narrows by the run_history row's `feature` and matches `json_extract(payload,'$.run_id')` (fsm_events has no run_id column).

**Shortcuts taken**:
- `counted_attempts` is `attempts` alone; ticket 06 must subtract the waits there.
- The failed-run set is in-process memory: a server restart between the decision and the settle (same function call chain, milliseconds) would lose it. Not worth a column.
- The freed task posts no `task_retry` broadcast or status line (no board broadcast fn on this path).

**For later tickets**:
- 06: add the "open question" exception in `settle_run_tasks` (return None and leave the task parked when the task has an open question) and subtract `waits` in `counted_attempts`.
- 12: loop tasks are skipped by `_owns_its_tasks` (`goal-loop` flow, `sched-` ids).

## Review findings (round 1, single review)

SPEC
- Done when 1: MET. 6 passed; covers no AGENT_DONE -> synthetic failed/task_unfinished; agent's own success on PTY-first and early-advance paths -> GET /runs/<id> failed with exactly 1 agent_invocations row; task back to pending and the next run claims it (attempts=2); at the limit failed, dependent blocked, one escalation; done task keeps success.
- Done when 2: MET.
- scope: OK (map.md and learnings.md are the feature's bookkeeping).
- test first: OK (a5a79e5f before the code; fails without it).

QUALITY
1. major src/pathly_orchestrator/supervisor/terminal.py: settle_run_tasks runs only on a clean end (early-advance return, and _synthesize_agent_done_if_missing on PTY-first and slow paths). A single run that exits non-zero (rate limit after retries, crash), times out, or is stopped raises before either call, so its claimed task stays in_progress with claimed_by = the dead run. Nothing frees it (reclaim_stale_claims is loop-scheduler only) and claim_task needs pending, so the next goal start can never claim it: the stuck-task outcome this ticket exists to remove. Fix: free the run's unfinished tasks on the exception path too (e.g. in the finally before _settle_spawn_identity, guarded by sys.exc_info()), free only, no extra AGENT_DONE or RUN_OUTCOME (run_history already becomes error there). Add a test with a non-zero exit_code.
2. minor terminal.py: the early-advance path still returns result_for_fsm with the agent's outcome success, and the PTY path's _pty_return carries no error, so on_done posts "goal run finished" phase done for a run that GET /runs/<id> and run_history call failed. Fix: put outcome failed / error task_unfinished on the returned result when settle_run_tasks returns an error.
3. minor terminal.py: on the early-advance path agent_done_data comes from read_last_agent_done(storage_path), the feature's latest AGENT_DONE, not necessarily this run's; it is passed as own_agent_done without checking run_id. Fix: pass it only when agent_done_data.get("run_id") == run_id, as terminal_reconcile does.
4. minor src/pathly_orchestrator/supervisor/terminal_identity.py: _settle_spawn_identity returns early when identity is falsy before take_run_failure, leaking the id in the module-level _failed_runs set; also an edited docstring line is over-long. Fix: call take_run_failure(run_id) before the `if not identity: return`, and rewrap.

REVIEW: FAIL
