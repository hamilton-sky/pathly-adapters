# team/test

Stage 4 — Test + Fix Loop. Invoked by the `team` orchestrator when FSM state is TESTING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> and **Live progress logging** — are composed in below from fragments. This body covers only
> the TESTING-stage specifics.

## Role

**Stage orchestrator: Testing**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

All events are appended to `pathly/plans/<feature>/EVENTS.jsonl` as JSON lines.
Every appended event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `pathly/plans/<feature>/STATE.json`.

- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>", "ts": "<iso-timestamp>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>", "ts": "<iso-timestamp>"}`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>", "ts": "<iso-timestamp>"}`.

## Phase 0 — Record test start time

Run: `python -c "import time; print(int(time.time()))"` and note the integer as `TEST_START`.

## Pre-gate

Read `pathly/plans/<feature>/PROGRESS.md`. Check every conversation row in the Conversation Breakdown table.
If any row status is not DONE: stop and report:
```
Not all conversations are complete. Route to team <feature> build first. Incomplete: Conv N
```

When all DONE: append `{"type": "IMPLEMENT_COMPLETE", "ts": "<iso-timestamp>"}` to EVENTS.jsonl. Confirm state is TESTING in STATE.json.

## Subagents (TESTING stage)

| Action | Spawn |
|---|---|
| Phase 1 — Analyze needs | `tester` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: tester` |
| Phase 3 — Test | `tester` (phase: test) |
| Fix failing criteria | `builder` |

## Rigor depth

- `lite`: testing may be limited to the verify commands and directly relevant checks from the plan.
- `standard`: tester verifies all acceptance criteria before retro.
- `strict`: tester must map every acceptance criterion to PASS / FAIL / NOT COVERED. Cannot proceed with NOT COVERED items.

## Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `tester` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Read pathly/plans/[feature]/USER_STORIES.md.
List what test infrastructure and context you need before verifying — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: test directories, source files touched | question: what test patterns, fixtures, and coverage gaps exist for the changed files?

Output `none` if the default test-context scout above is sufficient.
```
If the block is `none`, use only the default test-context scout in Phase 2.

log-phase PHASE_DONE analyze

## Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: tester`. Use the returned compressed summary as `## Test Context` in Phase 3.

log-phase PHASE_DONE scout

## Phase 3 — Test

log-phase PHASE_START test

Track `testRetryCount = 0`.

**Spawn** `tester` with `phase: test` and scout findings injected:
```
phase: test
Read pathly/plans/[feature]/USER_STORIES.md.
Run /test to verify each acceptance criterion.

## Test Context
[compressed findings]

For each criterion: PASS / FAIL / NOT COVERED.
If any FAIL or NOT COVERED: write pathly/plans/[feature]/feedback/TEST_FAILURES.md
using the shared feedback protocol format.
```

log-phase PHASE_DONE test

## Fix loop

After tester completes — check for `TEST_FAILURES.md`:

**If `TEST_FAILURES.md` exists:**
Increment `testRetryCount`. If `testRetryCount > 2`:
Stop — "Test failures unresolved after 2 fix cycles. Manual intervention required."

Log file created for TEST_FAILURES.md.

**Spawn** `builder`:
```
Read pathly/plans/[feature]/feedback/TEST_FAILURES.md.
Fix each failing or uncovered criterion.
Delete pathly/plans/[feature]/feedback/TEST_FAILURES.md when resolved.
```
After builder resolves: log file deleted for TEST_FAILURES.md. Re-spawn tester.

**If no TEST_FAILURES.md:** all criteria pass.

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

After the tester passes, run the Completion report with `agent: tester`, `conversation: 0`,
`result: PASS`, using `TEST_START` from Phase 0.

Return. Orchestrator determines next state from transition_rules.

## Live progress logging

When this skill says `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>`,
run the corresponding command below, filling in the actual feature name, agent role, and phase:

```bash
# On PHASE_START:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_START \
  --project-root "<project_root>"

# On PHASE_DONE:
pathly-fsm-call record-phase \
  --feature "<feature>" \
  --agent "<agent>" \
  --phase "<phase>" \
  --event-type PHASE_DONE \
  --project-root "<project_root>"
```

- `<feature>` — the feature slug (folder name under `pathly/plans/`)
- `<agent>` — the current agent role (`builder`, `reviewer`, `tester`, `designer`, etc.)
- `<phase>` — one of `analyze`, `scout`, `implement`, `review`, `test`, `plan`, `design`, `storm`

If `pathly-fsm-call` is unavailable or the server is not running, skip silently.
Phase logging must never block the main workflow.

## Completion report (usage parse + log-agent-done)

After the stage agent completes (Phase 3), parse the `<usage>` block from its response:
- `total_tokens`: the number after `total_tokens:` (0 if absent)
- `tool_uses`: the number after `tool_uses:` (0 if absent)
- `duration_ms`: the number after `duration_ms:` (0 if absent)

Compute the `wall_seconds` fallback: run
`python -c "import time; print(int(time.time()) - <STAGE>_START)"` using the `<STAGE>_START`
integer recorded at the start of this stage.

Then invoke the `log-agent-done` skill with:

`summary` should be a one-sentence description of what the agent did and the outcome (e.g. "Implemented Conv 1 — added auth middleware to api.ts, all tests pass").

```json
{"agent":"<agent>","feature":"<FEATURE>","conversation":<N>,"result":"<RESULT>","summary":"<one sentence describing what was done and the outcome>","total_tokens":<total_tokens>,"tool_uses":<tool_uses>,"duration_ms":<duration_ms>,"wall_seconds":<computed>}
```
(`wall_seconds` is the fallback computed from `<STAGE>_START`; `log-agent-done` prefers
`duration_ms` if > 0.)

Return. The orchestrator determines the next state from `transition_rules`.

## Scout choreography (analyze → scout → compress)

The stage agent (builder / reviewer / tester) declares what context it needs *before* doing the
work, scouts gather that context in parallel, and the findings are compressed into the work prompt.

### Phase 1 — Analyze

Spawn the stage agent with `phase: analyze`. It outputs a `## NEEDS_CONTEXT` block **only** —
the list of things it must know before implementing / reviewing / testing.

NEEDS_CONTEXT format (one entry per line):
```
  - type: scout | scope: <files or directories> | question: <specific question>
  - type: quick | question: <specific question>
```

Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2 (or use only the stage's
default scout entry, where one is defined).

### Phase 2 — Scout (parallel, max 4)

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: <stage agent>` + the question
- `type: scout` → spawn `scout` with `ROLE: <stage agent>` + scope + question

Compress all returned findings into a short summary and inject it into the Phase 3 work prompt
as the stage's findings section.

## Feedback protocol

All feedback files live in `pathly/plans/[feature]/feedback/`. File exists = issue open.
Absent = resolved.

Priority order (highest first): `HUMAN_QUESTIONS.md` › `ARCH_FEEDBACK.md` › `DESIGN_QUESTIONS.md` ›
`IMPL_QUESTIONS.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`

When you write a feedback file, use the shared feedback protocol formats and then report blocked.
The orchestrator routes the highest-priority open file to the responsible agent, one at a time,
before advancing.

### Guard — feedback-open check

Before spawning the stage agent, scan `pathly/plans/<feature>/feedback/`. If any file exists:
1. Identify the highest-priority file using the order above.
2. Log file created for that file.
3. Route to the responsible agent (see the stage's feedback routing section).
4. When resolved and the file is deleted: log file deleted. Re-scan.
5. Only proceed when no feedback files remain.

### Guard — retry-count check

Before routing any feedback file to its agent:
1. Check the retry count for `conv-N:FILE.md` in EVENTS.jsonl.
2. If > 2: write `HUMAN_QUESTIONS.md` with an escalation message, log file created for
   `HUMAN_QUESTIONS.md`. Stop and report the retry limit exceeded.
3. If ≤ 2: after routing the fix agent, log retry for `conv-N:FILE.md`.

Max 2 feedback cycles per conversation per feedback file. If exceeded, escalate to
`HUMAN_QUESTIONS.md`.

Exception: `IMPL_QUESTIONS.md` and `DESIGN_QUESTIONS.md` are clarification requests — exempt
from retry counting.
