---
name: Flow Diagram
---
# Adapter Integration Contract — Flow Diagram

```
Adapter                FSM
  |                    |
  | POST next_action   |
  |------------------->|
  |                    | reads STATE.json + EVENTS.jsonl
  |                    | returns decision + agent_hint
  |<-------------------|
  |                    |
  | dispatch native    |
  | agent using hint   |
  |                    |
  | POST complete_stage |
  |------------------->|
  |                    | re-checks gates / state
  |<-------------------|
  |                    | continue / block / escalate
```

Fallback path:
- `block` means surface the feedback and wait.
- `escalate` means stop and report the structural issue.
