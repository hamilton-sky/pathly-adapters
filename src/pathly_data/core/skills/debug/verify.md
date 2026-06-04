# debug/verify

VERIFYING stage. Confirm the fix actually resolves the original issue.

Parse `$ARGUMENTS`: `TOPIC` (the bug/issue identifier).

## Role

**Stage orchestrator: Debug Verify**
Validate the fix end-to-end: re-run the reproduction steps and confirm the symptom is gone.
Do not write new code here — only verify and report.

## Verification steps

log-phase PHASE_START analyze

Read `<feature_path>/ROOT_CAUSE.md` and `<feature_path>/FIX_SUMMARY.md`.
Understand what was changed and what the expected outcome is.

log-phase PHASE_DONE analyze

log-phase PHASE_START verify

1. Run the project's test suite (unit tests at minimum).
2. If a REPRO.md exists, walk through its steps and confirm the symptom no longer occurs.
3. Check for regressions in directly related code paths.

If verification passes:
- Write `<feature_path>/VERIFY.md` containing exactly `RESULT: PASS` on the first line.
- Transition state → DONE.

If verification fails:
- Write `<feature_path>/feedback/VERIFY_FAILURES.md` with a clear description of what still fails.
- Transition state → ROOT_CAUSE_FOUND so the fix can be reattempted.

log-phase PHASE_DONE verify

## FSM operations

All events appended to `<feature_path>/EVENTS.jsonl`.
Every event must include `"ts": "<iso-timestamp>"` using current ISO-8601 UTC time.

- **Transition state to X:** Write `<feature_path>/STATE.json` `{"current": "X"}`.
  Append `{"type": "STATE_TRANSITION", "to": "X", "ts": "<iso-timestamp>"}`.
