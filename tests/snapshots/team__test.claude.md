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
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

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

Each `log-phase PHASE_START <phase>` or `log-phase PHASE_DONE <phase>` marker is a mandatory
pipeline event. When you encounter one (or an inline `Run:` bash block replacing it), execute it immediately:

Run:
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

**Server availability — start-if-needed (same contract as log-agent-done):**

If `pathly-fsm-call` fails or the server is not reachable:
1. Start the server in the background: `pathly-fsm-http`
2. Wait 2 seconds, then retry the `record-phase` call once.
3. If the retry also fails: skip silently and continue — phase logging must never block execution.

This makes phase logging reliable on any adapter (Codex, Copilot, CLI) where the
FSM server is not automatically managed by the host environment.

## Completion report (AGENT_DONE)

After the stage agent completes, write an AGENT_DONE event **directly** to EVENTS.jsonl.
This is **mandatory** — the supervisor reads this field as the authoritative result.

1. Compute wall_seconds: `python3 -c "import time; print(int(time.time()) - BUILD_START)"`
2. Parse from the sub-agent's `<usage>` block: `total_tokens`, `tool_uses`, `duration_ms` (0 if absent).
3. Compute `cost_usd` from `total_tokens` and `model` using an 80/20 input/output token split:

   | Model prefix | Input $/MTok | Output $/MTok |
   |---|---|---|
   | `claude-opus-4` | 15.00 | 75.00 |
   | `claude-sonnet-4` | 3.00 | 15.00 |
   | `claude-haiku-4` | 0.80 | 4.00 |
   | other / unknown | — | set `cost_usd = 0.0` |

   Formula:
   ```
   in_est  = total_tokens * 0.8
   out_est = total_tokens * 0.2
   cost_usd = round((in_est / 1_000_000 * input_rate) + (out_est / 1_000_000 * output_rate), 6)
   ```

4. Write the event directly — **do not invoke a skill**, run this command:

```bash
python3 -c "
import json, datetime
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
  'type': 'AGENT_DONE',
  'agent': 'AGENT_ROLE',
  'model': 'MODEL_ID',
  'conversation': CONV_N,
  'result': 'DONE',
  'summary': 'SUMMARY_SENTENCE',
  'total_tokens': TOTAL_TOKENS,
  'tool_uses': TOOL_USES,
  'wall_seconds': WALL_SECONDS,
  'cost_usd': COST_USD,
  'ts': ts,
  'schema_version': 1,
}
path = '<feature_path>/EVENTS.jsonl'
with open(path, 'a', encoding='utf-8') as f:
    f.write(json.dumps(event) + chr(10))
print('AGENT_DONE written')
"
```

5. POST to the activity log — non-blocking; skip silently if server is unavailable:

```bash
pathly-fsm-call record-activity \
  --agent "AGENT_ROLE" \
  --feature "<feature>" \
  --summary "SUMMARY_SENTENCE" \
  --conversation CONV_N \
  --model "MODEL_ID" \
  --total-tokens TOTAL_TOKENS \
  --tool-uses TOOL_USES \
  --wall-seconds WALL_SECONDS \
  --cost-usd COST_USD
```

Replace the UPPER_CASE placeholders with actual values:
- `AGENT_ROLE` — e.g. `builder`, `reviewer`, `tester`
- `MODEL_ID` — model used in this stage (e.g. `claude-sonnet-4-6`)
- `CONV_N` — integer conversation number (0 for non-build stages)
- `SUMMARY_SENTENCE` — one sentence: what was done and the outcome
- `TOTAL_TOKENS`, `TOOL_USES`, `WALL_SECONDS` — from `<usage>` block or wall_seconds computation
- `COST_USD` — computed in step 3

`<feature>` and `<feature_path>` are pre-substituted by the runner — use the values as written.

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

All feedback files live in `<feature_path>/feedback/`. File exists = issue open.
Absent = resolved.

Priority order (highest first): `HUMAN_QUESTIONS.md` › `ARCH_FEEDBACK.md` › `DESIGN_QUESTIONS.md` ›
`IMPL_QUESTIONS.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`

When you write a feedback file, use the shared feedback protocol formats and then report blocked.
The orchestrator routes the highest-priority open file to the responsible agent, one at a time,
before advancing.

### Guard — feedback-open check

Before spawning the stage agent, scan `<feature_path>/feedback/`. If any file exists:
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
