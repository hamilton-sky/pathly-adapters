# team/test

Stage 4 — Test + Fix Loop. Invoked by the `team` orchestrator when FSM state is TESTING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

## FSM operations

All events are appended to `plans/<feature>/EVENTS.jsonl` as JSON lines.
State snapshots are written to `plans/<feature>/STATE.json`.

- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>"}`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>"}`.

## Phase 0 — Record test start time

Run: `python -c "import time; print(int(time.time()))"` and note the integer as `TEST_START`.

## Pre-gate

Read `plans/<feature>/PROGRESS.md`. Check every conversation row in the Conversation Breakdown table.
If any row status is not DONE: stop and report:
```
Not all conversations are complete. Route to team <feature> build first. Incomplete: Conv N
```

When all DONE: append `{"type": "IMPLEMENT_COMPLETE"}` to EVENTS.jsonl. Confirm state is TESTING in STATE.json.

## Subagents

| Action | Spawn |
|---|---|
| Phase 1 — Analyze needs | `tester` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: tester` (parallel, max 4) |
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

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: tester` + the question
- `type: scout` → spawn `scout` with `ROLE: tester` + scope + question

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
- Stop signal: log human response "stop". Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

**Write-or-delete transition artifact:**
- If tests still failing after fix loop: TEST_FAILURES.md already exists — keep it.
- If all tests pass: delete `<storage_path>/feedback/TEST_FAILURES.md` if it exists.

## Record completion

After the tester agent completes (Phase 3), parse the `<usage>` block from its response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Compute wall_seconds from `TEST_START` (recorded in Phase 0 / Pre-gate section) as fallback if duration_ms is 0.
Append `{"type": "AGENT_DONE", "agent": "tester", "model": "<model>", "conversation": 0, "result": "PASS", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0, "tool_uses": <tool_uses>, "wall_seconds": <computed>, "ts": "<iso-timestamp>"}` to `plans/<feature>/EVENTS.jsonl`.

Then invoke the `record-cost` skill with:
```json
{"agent":"tester","feature":"<FEATURE>","summary":"All acceptance tests pass","conversation":0,"wall_seconds":<computed>,"total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>}
```

Return. Orchestrator determines next state from transition_rules.
