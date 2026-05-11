# team-flow/test

Stage 4 — Test + Fix Loop. Invoked by the `team-flow` orchestrator when FSM state is TESTING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

## FSM operations

All events are appended to `plans/<feature>/EVENTS.jsonl` as JSON lines.
State snapshots are written to `plans/<feature>/STATE.json`.

- **Transition state to X:** Write STATE.json `{"current": "X"}`. Append `{"type": "STATE_TRANSITION", "to": "X"}`.
- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>"}`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>"}`.

## Pre-gate

Read `plans/<feature>/PROGRESS.md`. Check every conversation row in the Conversation Breakdown table.
If any row status is not DONE: stop and report:
```
Not all conversations are complete. Route to team-flow <feature> build first. Incomplete: Conv N
```

When all DONE: append `{"type": "IMPLEMENT_COMPLETE"}` to EVENTS.jsonl. Confirm state is TESTING in STATE.json.

## Subagents

| Action | Spawn |
|---|---|
| Gather test context | `scout` with `ROLE: tester` |
| Verify acceptance criteria | `tester` |
| Fix failing criteria | `builder` |

## Rigor depth

- `lite`: testing may be limited to the verify commands and directly relevant checks from the plan.
- `standard`: tester verifies all acceptance criteria before retro.
- `strict`: tester must map every acceptance criterion to PASS / FAIL / NOT COVERED. Cannot proceed with NOT COVERED items.

---

## Pre-tester scout

**Spawn** `scout` with `ROLE: tester`:
```
ROLE: tester
What test patterns, existing test fixtures, and coverage gaps exist for the files changed in [feature]?
Scope: test directories, source files touched, existing test helpers/fixtures.
Return: existing test patterns to follow, missing coverage areas, and any test commands specific to this module.
```
Inject findings as `## Test Context` into the tester spawn prompt.

## Tester spawn

Track `testRetryCount = 0`.

**Spawn** `tester`:
```
Read plans/[feature]/USER_STORIES.md.
Run /test to verify each acceptance criterion.

## Test Context
[scout findings]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write plans/[feature]/feedback/TEST_FAILURES.md
using the shared feedback protocol format.
```

## Fix loop

After tester completes — check for `TEST_FAILURES.md`:

**If `TEST_FAILURES.md` exists:**
Increment `testRetryCount`. If `testRetryCount > 2`:
Stop — "Test failures unresolved after 2 fix cycles. Manual intervention required."

Log file created for TEST_FAILURES.md.

**Spawn** `builder`:
```
Read plans/[feature]/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete plans/[feature]/feedback/TEST_FAILURES.md when resolved.
```
After builder resolves: log file deleted for TEST_FAILURES.md. Re-spawn tester.

**If no TEST_FAILURES.md:** all criteria pass.

---

## Advance

If not autoFlow — pause:
```
[Stage 4 — Test complete]
All acceptance criteria: PASS.
Reply 'done' to proceed to retro.
```
- Proceed signal: log human response with reply value. Advance.
- Stop signal: log human response "stop". Write STATE.json with current state. Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

Transition state → RETRO.
Route back to `team-flow [FEATURE] [rigor] [autoFlow]`. (Orchestrator routes to retro.)
