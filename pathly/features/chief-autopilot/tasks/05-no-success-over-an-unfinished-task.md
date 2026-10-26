# Fail a single run that leaves its task unfinished, and free the task

Type: task
Status: open
Blocked by: 11
Test first: yes
Level: 2
Touches: src/pathly_orchestrator/supervisor/terminal_reconcile.py, src/pathly_orchestrator/supervisor/run_task_outcome.py (new), src/pathly_orchestrator/db/queries/comms_tasks_by_run.py (new), src/pathly_orchestrator/db/queries/run_history_read.py, tests/runner_supervisor/test_unfinished_task_outcome.py, src/pathly_orchestrator/CLAUDE.md, tests/INDEX.md, tests/runner_supervisor/INDEX.md

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
