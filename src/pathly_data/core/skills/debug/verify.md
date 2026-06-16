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
- Call `pathly-fsm-call complete-stage --flow debug --topic $TOPIC --project-root $PROJECT_ROOT`; the FSM computes the next state and writes STATE.json.

If verification fails:
- Write `<feature_path>/feedback/VERIFY_FAILURES.md` with a clear description of what still fails.
- Call `pathly-fsm-call complete-stage --flow debug --topic $TOPIC --project-root $PROJECT_ROOT` with the feedback file present; the FSM gates on its existence and routes via transition_rules.

log-phase PHASE_DONE verify

## FSM operations

State transitions are written to the central DB via the FSM server.
Every event must include `"ts": "<iso-timestamp>"` using current ISO-8601 UTC time.

- **Transition state to X:** Call `pathly-fsm-call complete-stage --flow <flow> --topic <topic> --project-root <project_root>`.
  The FSM computes the next state from transition_rules and writes `<feature_path>/STATE.json` as a mirror of the DB state.
