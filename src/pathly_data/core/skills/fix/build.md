# fix/build

FIXING stage for quick-fix flow. Fast, focused, minimal — one targeted change.

Parse `$ARGUMENTS`: `TOPIC` (the fix identifier).

## Role

**Stage orchestrator: Quick Fix**
Apply a single, well-scoped fix. No multi-conversation planning, no PROGRESS.md tracking.
Read the issue description, locate the code, apply the minimal change, verify it passes.

log-phase PHASE_START analyze

Understand the issue. Read any context files in `<feature_path>/`.
Identify the exact change needed.

log-phase PHASE_DONE analyze

log-phase PHASE_START implement

Apply the fix. Run typecheck / lint / tests. Confirm passing.

log-phase PHASE_DONE implement

## FSM operations

All events appended to `<feature_path>/EVENTS.jsonl`.
Every event must include `"ts": "<iso-timestamp>"` using current ISO-8601 UTC time.

- **Transition state to X:** Write `<feature_path>/STATE.json` `{"current": "X"}`.
  Append `{"type": "STATE_TRANSITION", "to": "X", "ts": "<iso-timestamp>"}`.
