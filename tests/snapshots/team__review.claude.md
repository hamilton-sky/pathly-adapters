# team/review

Stage 3b — Review. Invoked by the `team` orchestrator when FSM state is REVIEWING.
Runs reviewer for the current conversation, handles feedback loops, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`. Conv N is the most recent BUILDING conversation
(last row in PROGRESS.md that is not yet DONE).

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the REVIEWING-stage specifics.

## Role

**Stage orchestrator: Reviewing**
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
- **Log retry:** Append `{"type": "RETRY", "key": "conv-N:FILE.md", "ts": "<iso-timestamp>"}`.
- **Check retry count:** Count RETRY events in EVENTS.jsonl where `key = "conv-N:FILE.md"`.
- **Log human response:** Append `{"type": "HUMAN_RESPONSE", "value": "<value>", "ts": "<iso-timestamp>"}`.
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Subagents (REVIEWING stage)

| Action | Spawn |
|---|---|
| Phase 1 — Analyze changes | `reviewer` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: reviewer` |
| Phase 3 — Review | `reviewer` (phase: review) |
| Fix architectural violations | `architect` |
| Fix implementation violations | `builder` |

## Rigor gate

- `lite`: reviewer runs once after the **final** builder conversation, unless any of these apply:
  feedback files exist, risky files were touched, or user preference requires per-conversation review.
  If this is not the final conversation and none of those conditions apply → skip directly to Advance.
- `standard` or `strict`: reviewer runs after **every** builder conversation.

log-phase PHASE_START review

## Phase 0 — Record review start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `REVIEW_START`.

## Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `reviewer` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Conv N of [feature] — scan the diff to identify what context you need before reviewing.
Run: git diff HEAD~1 HEAD
Read pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md if it exists.
List what you need — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: CLAUDE.md, .claude/rules/, pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md | question: what architectural rules and coding conventions apply to the changed files?

Output `none` if the default rules scout above is sufficient.
```
If the block is `none`, use only the default rules scout in Phase 2.

log-phase PHASE_DONE analyze

## Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: reviewer`. Compress all findings into a short summary for Phase 3.

log-phase PHASE_DONE scout

## Phase 3 — Review

log-phase PHASE_START review

**Spawn** `reviewer` with `phase: review` and scout findings injected:
```
phase: review
Review the changes from conversation N of [feature].
Run: git diff HEAD~1 HEAD (or git diff --staged if not yet committed).

## Applicable Rules and Context (from pre-review scout)
[compressed findings]

Check against these rules and pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md.
If architectural violations found: write pathly/plans/[feature]/feedback/ARCH_FEEDBACK.md
If implementation violations found: write pathly/plans/[feature]/feedback/REVIEW_FAILURES.md
Use the shared feedback protocol formats.
If all clear: report PASS.
```

log-phase PHASE_DONE review

## Feedback routing after reviewer

Apply the Feedback protocol retry-count guard before routing each file (escalate to
HUMAN_QUESTIONS.md when the retry limit is exceeded).

### If `ARCH_FEEDBACK.md` exists

After the retry guard, **spawn** `architect`:
```
Read pathly/plans/[feature]/feedback/ARCH_FEEDBACK.md.
Redesign the affected architecture in pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md,
or pathly/plans/[feature]/IMPLEMENTATION_PLAN.md for lite plans without ARCHITECTURE_PROPOSAL.md.
If phases need to change, update IMPLEMENTATION_PLAN.md.
Delete pathly/plans/[feature]/feedback/ARCH_FEEDBACK.md when resolved.
Report: what changed in the design.
```
After architect resolves: log file deleted for ARCH_FEEDBACK.md.
Return. Orchestrator determines next state from transition_rules.

### If `REVIEW_FAILURES.md` exists (no ARCH_FEEDBACK.md)

After the retry guard, **spawn** `builder`:
```
Read pathly/plans/[feature]/feedback/REVIEW_FAILURES.md.
Fix each violation listed. Do not change anything outside the listed violations.
Delete pathly/plans/[feature]/feedback/REVIEW_FAILURES.md when all fixed.
```

**Guard — zero-diff stall check** (before re-spawning reviewer):
```bash
git diff HEAD -- . ":(exclude)pathly/plans/"
```
- If command fails: skip check, print `[FSM WARNING] git diff failed — skipping zero-diff check`.
- If output is **empty** (no code changed):
  Write `pathly/plans/[feature]/feedback/HUMAN_QUESTIONS.md`:
  ```
  [STALL] Conversation N — builder and reviewer in zero-diff loop.
  Builder claimed to fix REVIEW_FAILURES.md but no code changed.
  Human decision required: accept as-is, override the rule, or rewrite the conversation scope.
  ```
  Append `{"type": "NO_DIFF_DETECTED", "ts": "<iso-timestamp>"}` to EVENTS.jsonl.
  Stop: "Zero-diff loop detected for Conv N. Escalated to HUMAN_QUESTIONS.md."
- If output is **non-empty**: re-run from Phase 1 — Analyze above.

### If no feedback files — PASS

Run the Completion report with `agent: reviewer`, `result: PASS`, using `REVIEW_START` from Phase 0.

## Advance

If not autoFlow — pause:
```
[Stage 3 — Conversation N complete + reviewed]
Reviewer: PASS. Commit your changes now.
Reply 'continue' for the next conversation, or 'stop' to pause here.
```
- Proceed signal: log human response with reply value. Advance.
- Stop signal: log human response "stop". Halt.
- Unrecognised: re-prompt without logging.

If autoFlow: log human response "auto-advance".

Mark Conv N as DONE in `pathly/plans/[feature]/PROGRESS.md`.

**Write-or-delete transition artifacts:**
- If REVIEW_FAILURES.md was written this run: it already exists — keep it.
  If reviewer passed cleanly (no REVIEW_FAILURES.md written): delete `<storage_path>/feedback/REVIEW_FAILURES.md` if it exists.

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
3. Write the event directly — **do not invoke a skill**, run this command:

```bash
python3 -c "
import json, datetime, sys
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
event = {
  'type': 'AGENT_DONE',
  'agent': 'AGENT_ROLE',
  'model': 'claude-sonnet-4-6',
  'conversation': CONV_N,
  'result': 'DONE',
  'summary': 'SUMMARY_SENTENCE',
  'total_tokens': TOTAL_TOKENS,
  'tool_uses': TOOL_USES,
  'wall_seconds': WALL_SECONDS,
  'cost_usd': 0.0,
  'ts': ts,
  'schema_version': 1,
}
path = '<feature_path>/EVENTS.jsonl'
with open(path, 'a', encoding='utf-8') as f:
    f.write(json.dumps(event) + chr(10))
print('AGENT_DONE written')
"
```

Replace the UPPER_CASE placeholders with actual values:
- `AGENT_ROLE` — e.g. `builder`, `reviewer`, `tester`
- `CONV_N` — integer conversation number (0 for non-build stages)
- `SUMMARY_SENTENCE` — one sentence: what was done and the outcome
- `TOTAL_TOKENS`, `TOOL_USES`, `WALL_SECONDS` — from `<usage>` block or wall_seconds computation

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

## Sub-agent spawning rules

This stage runs on a host that can spawn sub-agents (Task / subagent capability).

- **Never execute work yourself** — spawn the right subagent for each step.
- Treat the FSM as a deterministic filesystem machine: read disk, process one event, emit one action.
- After every agent completes, check for feedback files before advancing.
- Spawn scouts and parallel workers up to a maximum of 4 at once.

Map each action to its subagent (the stage skill lists the exact roles for that stage):

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Review changes | `reviewer` |
| Verify acceptance criteria | `tester` |
| Clarify requirement | `planner` |
| Clarify / redesign architecture | `architect` |
| Scout context | `scout` or `quick` (with `ROLE:` set to the stage agent) |
