# Do not report success while the run's task is unfinished

Type: task
Status: open
Blocked by: —
Test first: yes

Spike S6: a goal run with the default `single` executor ended `done` with a synthetic
`AGENT_DONE` `outcome: "success"` while the task it claimed stayed `in_progress` and the file it
was asked for did not exist. `supervisor/terminal_reconcile.py::_synthesize_agent_done_if_missing`
hard-codes `"outcome": "success"`, and the loop executor reads `AGENT_DONE.outcome` as the pass/fail
signal (`_outcome_is_failure`).

When an executor-owned run (board single, goal single, goal loop task) ends, look up the tasks
still `in_progress` with `claimed_by` this run (`db/queries/comms_tasks.py`; add a read query in
its own small file if `comms_tasks.py` has no room). If there is at least one:

- the synthetic `AGENT_DONE` (when one is written) carries `"outcome": "failed"` and
  `"error": "task_unfinished"`, and
- an agent-written `AGENT_DONE` that says `success` is overridden for the run's result the same
  way (write a `RUN_OUTCOME_OVERRIDE` event or patch the run's outcome; pick the one the loop
  executor and `GET /runs/<id>` already read, and say which in the Answer).

The task itself is left to the existing retry path (`supervisor/task_retry.py`), which already
puts a failed attempt back to `pending` or `blocked` by attempt count. A run whose tasks are all
`done` is unchanged. Ticket 06 adds the case where the agent asked a question.

## Not in this ticket

- Questions: ticket 06 reuses this lookup and adds the `waiting_for_answer` reason.
- Flow (FSM) runs: their gates (`require_tasks_done`, `task_checks`) already judge tasks.

## Done when

- `python -m pytest tests/runner_supervisor/test_unfinished_task_outcome.py -q -p no:cacheprovider`
  passes and covers: a single-executor run that ends with its claimed task `in_progress` and no
  `AGENT_DONE` gets a synthetic one with `outcome: failed`, `error: task_unfinished`; the same
  with an agent `AGENT_DONE` of `success` is reported failed; a run whose task is `done` keeps
  `success`; the task goes through the retry path (attempt counted).
- All existing tests under `tests/runner_supervisor` and `tests/dag_goals` still pass.

```check
$ python -m pytest tests/runner_supervisor/test_unfinished_task_outcome.py -q -p no:cacheprovider
exit 0
prints passed
$ python -m pytest tests/runner_supervisor tests/dag_goals -q -p no:cacheprovider
exit 0
```

## Reference

- spike19-part-b-report.md § 5 ("The run ended done, with a synthetic AGENT_DONE outcome: success")
- `src/pathly_orchestrator/supervisor/terminal_reconcile.py`, `src/pathly_orchestrator/supervisor/task_retry.py`

## Answer
