# team/build

Stage 3a — Implement. Invoked by the `team` orchestrator when FSM state is BUILDING.
Executes one TODO conversation (analyze → scout → implement), then transitions to REVIEWING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the BUILDING-stage specifics.

## Role

**Stage orchestrator: Building**
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

## Subagents (BUILDING stage)

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Clarify requirement | `planner` |
| Clarify architecture | `architect` |

## Execution

Read `pathly/plans/[feature]/PROGRESS.md`. Find the first conversation row with status TODO. This is Conv N.

### Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `builder` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Route to continue [feature] conversation N.
List what you need to know before implementing — output NEEDS_CONTEXT block only.
```

log-phase PHASE_DONE analyze

### Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: builder`. Use the returned compressed summary as Scout Findings.

log-phase PHASE_DONE scout

### Phase 2.5 — Record build start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `BUILD_START`.

### Phase 3 — Implement

log-phase PHASE_START implement

**Spawn** `builder` with `phase: implement`:
```
phase: implement
Route to continue [feature] in manual mode.
Execute conversation N only. Verify. Do NOT update PROGRESS.md — the orchestrator handles that after the reviewer passes.

## Scout Findings
[compressed summary — or "none" if Phase 2 was skipped]

If you hit requirement ambiguity (what should this do?): write pathly/plans/[feature]/feedback/IMPL_QUESTIONS.md
If you hit a technical blocker (how is this possible?): write pathly/plans/[feature]/feedback/DESIGN_QUESTIONS.md
Use the shared feedback protocol formats, then report blocked.
Report: files changed, verify result, stories delivered.
```

log-phase PHASE_DONE implement

### Feedback routing after builder

Feedback file priority, the feedback-open guard, and the retry-count guard are defined in the
Feedback protocol fragment. Route the highest-priority open file to the agent below.

**If `IMPL_QUESTIONS.md` exists** ([REQ] tagged):
**Spawn** `planner`:
```
Read pathly/plans/[feature]/feedback/IMPL_QUESTIONS.md.
Answer each [REQ] question — clarify in USER_STORIES.md or CONVERSATION_PROMPTS.md.
Delete pathly/plans/[feature]/feedback/IMPL_QUESTIONS.md when resolved.
```
After resolved: log file deleted for IMPL_QUESTIONS.md. Re-run Phase 3. Do not log retry.

**If `DESIGN_QUESTIONS.md` exists** ([ARCH] tagged):
**Spawn** `architect`:
```
Read pathly/plans/[feature]/feedback/DESIGN_QUESTIONS.md.
Resolve each [ARCH] question — update ARCHITECTURE_PROPOSAL.md (or IMPLEMENTATION_PLAN.md for lite plans).
Delete pathly/plans/[feature]/feedback/DESIGN_QUESTIONS.md when resolved.
```
After resolved: log file deleted for DESIGN_QUESTIONS.md. Re-run Phase 3. Do not log retry.

Both files can exist simultaneously. Route one at a time using the priority order. After both resolve → builder re-implements.

## Transition to review

After Phase 3 completes with no blocking feedback files:

### Phase 3.5 — Write VERIFY.md

Write `pathly/plans/<feature>/VERIFY.md` with this exact content (first line must be exact):
```
RESULT: PASS
Verified: conversation N complete — <one-sentence summary of what was verified and the outcome>
```

Replace `<feature>` with the feature slug and `N` with the conversation number.
The first line **must** be `RESULT: PASS` verbatim (case-sensitive, no leading whitespace).

Then run the Completion report with `agent: builder`, `result: DONE`, using `BUILD_START` from Phase 2.5.

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
path = 'pathly/plans/<feature>/EVENTS.jsonl'
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

`<feature>` is pre-substituted by the runner — use the value as written.

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
