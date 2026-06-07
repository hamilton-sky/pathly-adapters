# debug/build

FIXING stage. The root cause has been diagnosed — now implement the targeted fix.

Parse `$ARGUMENTS`: `TOPIC` (the bug/issue identifier).

## Role

**Stage orchestrator: Debug Fix**
Apply the fix identified in the root-cause analysis. Stay strictly within the diagnosed
scope — do not refactor, clean up, or improve unrelated code.

## Context files

Before touching any code, read:
- `<feature_path>/ROOT_CAUSE.md` — diagnosis and agreed fix approach
- `<feature_path>/REPRO.md` — reproduction steps (if present)

log-phase PHASE_START analyze

Read ROOT_CAUSE.md. Identify the exact files and lines to change. Confirm the fix approach.

log-phase PHASE_DONE analyze

log-phase PHASE_START implement

Apply the fix. Keep changes minimal and targeted to the diagnosed root cause.
Run the project's verify command (typecheck / lint / unit tests) and confirm it passes.
Write `<feature_path>/FIX_SUMMARY.md` with a one-paragraph description of what was changed and why.

log-phase PHASE_DONE implement

## FSM operations

State transitions are written to the central DB via the FSM server.
Every event must include `"ts": "<iso-timestamp>"` using current ISO-8601 UTC time.

- **Transition state to X:** Write `<feature_path>/STATE.json` `{"current": "X"}`.
  Call `pathly-fsm-call record-activity` to log the event to the central DB.
