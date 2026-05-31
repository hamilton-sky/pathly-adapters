---
name: Flow Diagram
---
# Adapter Integration Contract — Flow Diagram

## Normal flow (decision = continue)

```
Adapter                          FSM
  |                               |
  | POST /next_action             |
  |------------------------------>|
  |                               | reads STATE.json + EVENTS.jsonl
  |                               | returns { decision:"continue", current_state, agent_hint, ... }
  |<------------------------------|
  |                               |
  | dispatch native agent         |
  | using agent_hint.role         |
  | and agent_hint.instructions   |
  |                               |
  | POST /complete_stage          |
  |------------------------------>|
  |                               | re-checks gates / state
  |                               | returns { decision:"continue", current_state:<new>, agent_hint, ... }
  |<------------------------------|
  |                               |
  | (loop until done: true)       |
```

## Blocked flow (decision = block — agent-resolvable)

```
  | POST /complete_stage          |
  |------------------------------>|
  |                               | finds open feedback file; target is a Pathly agent
  |                               | returns { decision:"block", target_agent:"builder", file:... }
  |<------------------------------|
  |                               |
  | route to target_agent         |
  | with feedback file as context |
  |                               |
  | POST /complete_stage          |  (resolved_files: [filename])
  |------------------------------>|
  |                               | deletes feedback file, advances
  |<------------------------------|
```

## Escalate flow (decision = escalate — human-resolvable)

```
  | POST /next_action or          |
  | POST /complete_stage          |
  |------------------------------>|
  |                               | target_agent="human", corrupt state,
  |                               | or retry limit exceeded
  |                               | returns { decision:"escalate", blocked:true, ... }
  |<------------------------------|
  |                               |
  | STOP — surface to user        |
  | (do not automate escalate)    |
```

## Key contract rules

- Both `/next_action` and `/complete_stage` always return `current_state` (never `next_state`).
- `agent_hint.role` = dispatch label (`"worker"` or `"explorer"`).
- `agent_hint.instructions` = full delegated prompt.
- `codex_subagent` = frozen compat with old keys (`codex_role`, `pathly_agent`) — read by legacy consumers only.
- `block` → automated agent retry is safe. `escalate` → stop and involve the user.
