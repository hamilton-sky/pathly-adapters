# Re-queue a stage that finished across a newer binding decision instead of advancing it

Type: task
Status: open
Blocked by: 07
Test first: yes

A headless run takes no input after spawn, so a builder halfway through a stage would finish on
the old rule (SPEC.md § C6.3). Add `src/pathly_orchestrator/supervisor/directive_check.py`:

- `stale_directives(conn, run) -> list[dict]`: binding decisions on the run's boards targeting
  its role (`to_agent IN (role, '*')`) whose `ts` is after the run's spawn time.
- Where the supervisor handles a stage's terminal result (FSM loop and the loop/goal executors),
  call it before advancing. Non-empty → record outcome `stale_directive` on the run, post a
  `status` naming the directive ids, and re-queue the same stage; the next spawn's governance
  block carries the directive (the binding-directives ticket). Empty → unchanged.
- At most one stale re-queue per stage per directive, so a directive posted in a loop cannot
  re-run a stage forever.

## Not in this ticket

- Interrupting a run in flight.

## Done when

- `python -m pytest tests/runner_supervisor/test_stale_directive.py -q` passes and covers: a
  directive posted after a builder spawn and before its exit → the stage is re-queued, not
  advanced, and the second spawn's prompt contains the directive; a directive posted before the
  spawn → advances normally; a directive targeting `reviewer` does not re-queue a builder stage;
  the same directive never re-queues a stage twice.

```check
$ python -m pytest tests/runner_supervisor/test_stale_directive.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C6; `supervisor/orchestrator.py`, `supervisor/orchestrator_stage.py`,
  `supervisor/drain.py` (where results are handled)
- Ticket 07's Answer

## Answer
