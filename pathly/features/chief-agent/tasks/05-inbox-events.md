# Feed board events into the chief inbox and debounce them into one turn

Type: task
Status: open
Blocked by: 04
Test first: yes

Add `src/pathly_orchestrator/supervisor/chief_inbox.py` (SPEC.md § C1, § C4):

- `notify(project_root, kind, ref_id, payload)`: enqueue, then schedule one `run_chief_turn` after
  `chief.debounce_ms` (app setting, default 3000). Further events inside the window join the same
  turn; a turn already scheduled is not scheduled twice.
- Only when `chief.enabled` is true (app setting, default false). When false, events are not
  enqueued and nothing spawns; a human message still starts a turn.
- Call sites, one line each:
  - agent question: `supervisor/interactions.py::_await_agent_question` → `kind="agent_question"`
    with the question topic;
  - run finished: where the supervisor settles a run (the same place `run_history` is settled) →
    `kind="run_done"` with run id and outcome;
  - escalation posted: the comms write path when `type="escalation"` → `kind="escalation"`;
  - goal blocked: the goal executor's blocked/escalated exit → `kind="goal_blocked"`.

## Not in this ticket

- Accepting the chief's answers to agent questions: the relay ticket.

## Done when

- `python -m pytest tests/runner_supervisor/test_chief_inbox.py -q` passes and covers: ten
  events within one debounce window → exactly one turn whose batch holds all ten; with
  `chief.enabled=false` an agent question enqueues nothing and spawns nothing; each of the four
  call sites enqueues its kind (using the real call site with a fake turn runner).

```check
$ python -m pytest tests/runner_supervisor/test_chief_inbox.py -q -p no:cacheprovider
exit 0
prints passed
```

## Reference

- SPEC.md § C1 (debounce), § F Q1 (why off by default)
- `supervisor/interactions.py`, `supervisor/terminal_identity.py::_settle_spawn_identity`,
  `supervisor/goal_executor.py`, `blueprints/comms/messages_write.py`
- Ticket 04's Answer

## Answer
