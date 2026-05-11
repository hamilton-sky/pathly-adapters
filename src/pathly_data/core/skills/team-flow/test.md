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
| Phase 1 — Analyze needs | `tester` (phase: analyze) |
| Phase 2 — Scout context | `scout-flow` with `ROLE: tester` |
| Phase 3 — Test | `tester` (phase: test) |
| Fix failing criteria | `builder` |

## Rigor depth

- `lite`: testing may be limited to the verify commands and directly relevant checks from the plan.
- `standard`: tester verifies all acceptance criteria before retro.
- `strict`: tester must map every acceptance criterion to PASS / FAIL / NOT COVERED. Cannot proceed with NOT COVERED items.

---

## Phase 1 — Analyze

**Spawn** `tester` with `phase: analyze`:
```
phase: analyze
Read plans/[feature]/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.

NEEDS_CONTEXT format (one entry per line):
  - type: scout | scope: <test directories or source files> | question: <specific question>
  - type: quick | question: <specific question>

Always include at minimum:
  - type: scout | scope: test directories, source files touched | question: what test patterns, fixtures, and coverage gaps exist for the changed files?

Output `none` if the default test-context scout above is sufficient.
```
Parse the `## NEEDS_CONTEXT` block. If it says `none`, use only the default test-context scout in Phase 2.

## Phase 2 — Scout

Call **scout-flow** with:
- `NEEDS_CONTEXT`: the block from Phase 1
- `ROLE: tester`
- `FEATURE: <feature>`

Use the returned compressed summary as `## Test Context` in Phase 3.

## Phase 3 — Test

Track `testRetryCount = 0`.

**Spawn** `tester` with `phase: test` and scout findings injected:
```
phase: test
Read plans/[feature]/USER_STORIES.md.
Run /test to verify each acceptance criterion.

## Test Context
[compressed findings]

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
