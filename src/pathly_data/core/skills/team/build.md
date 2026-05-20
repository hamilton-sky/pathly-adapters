# team/build

Stage 3a — Implement. Invoked by the `team` orchestrator when FSM state is BUILDING.
Executes one TODO conversation (analyze → scout → implement), then transitions to REVIEWING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

## FSM operations

All events are appended to `plans/<feature>/EVENTS.jsonl` as JSON lines.
State snapshots are written to `plans/<feature>/STATE.json`.

- **Log file created:** Append `{"type": "FILE_CREATED", "file": "<filename>"}`.
- **Log file deleted:** Append `{"type": "FILE_DELETED", "file": "<filename>"}`.
- **Log retry:** Append `{"type": "RETRY", "key": "conv-N:FILE.md"}`.
- **Check retry count:** Count RETRY events in EVENTS.jsonl where `key = "conv-N:FILE.md"`.

## Core rules

- Never execute work yourself — spawn the right subagent for each step.
- Treat the FSM as a deterministic filesystem machine: read disk, process one event, emit one action.
- After every agent completes, check for feedback files before advancing.
- Max 2 feedback cycles per conversation per feedback file. If exceeded, escalate to HUMAN_QUESTIONS.md.

## Subagents

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Clarify requirement | `planner` |
| Clarify architecture | `architect` |

## Feedback file priority (for routing blocked builders)

All files live in `plans/[feature]/feedback/`. File exists = issue open. Absent = resolved.

Priority order: `HUMAN_QUESTIONS.md` › `ARCH_FEEDBACK.md` › `DESIGN_QUESTIONS.md` ›
`IMPL_QUESTIONS.md` › `REVIEW_FAILURES.md` › `TEST_FAILURES.md`

## Guard — feedback-open check

Before spawning builder, scan `plans/<feature>/feedback/`. If any file exists:
1. Identify highest-priority file using the order above.
2. Log file created for that file.
3. Route to the responsible agent (see feedback routing below).
4. When resolved and file deleted: log file deleted. Re-scan.
5. Only proceed when no feedback files remain.

## Guard — retry-count check

Before routing any feedback file to its agent:
1. Check retry count for `conv-N:FILE.md` in EVENTS.jsonl.
2. If > 2: write HUMAN_QUESTIONS.md with escalation message, log file created for HUMAN_QUESTIONS.md. Stop and report retry limit exceeded.
3. If ≤ 2: after routing the fix agent, log retry for `conv-N:FILE.md`.

Exception: `IMPL_QUESTIONS.md` and `DESIGN_QUESTIONS.md` are clarification requests — exempt from retry counting.

---

## Execution

Read `plans/[feature]/PROGRESS.md`. Find the first conversation row with status TODO. This is Conv N.

### Phase 1 — Analyze

**Spawn** `builder` with `phase: analyze`:
```
phase: analyze
Route to continue [feature] conversation N.
List what you need to know before implementing — output NEEDS_CONTEXT block only.
```
Parse the `## NEEDS_CONTEXT` block. If it says `none`, skip Phase 2.

### Phase 2 — Scout (if NEEDS_CONTEXT has entries)

Spawn all NEEDS_CONTEXT entries in parallel (max 4 total):
- `type: quick` → spawn `quick` with `ROLE: builder` + the question
- `type: scout` → spawn `scout` with `ROLE: builder` + scope + question

Use the returned compressed summary as Scout Findings.

### Phase 2.5 — Record build start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `BUILD_START`.

### Phase 3 — Implement

**Spawn** `builder` with `phase: implement`:
```
phase: implement
Route to continue [feature] in manual mode.
Execute conversation N only. Verify. Do NOT update PROGRESS.md — the orchestrator handles that after the reviewer passes.

## Scout Findings
[compressed summary — or "none" if Phase 2 was skipped]

If you hit requirement ambiguity (what should this do?): write plans/[feature]/feedback/IMPL_QUESTIONS.md
If you hit a technical blocker (how is this possible?): write plans/[feature]/feedback/DESIGN_QUESTIONS.md
Use the shared feedback protocol formats, then report blocked.
Report: files changed, verify result, stories delivered.
```

### Feedback routing after builder

**If `IMPL_QUESTIONS.md` exists** ([REQ] tagged):
**Spawn** `planner`:
```
Read plans/[feature]/feedback/IMPL_QUESTIONS.md.
Answer each [REQ] question — clarify in USER_STORIES.md or CONVERSATION_PROMPTS.md.
Delete plans/[feature]/feedback/IMPL_QUESTIONS.md when resolved.
```
After resolved: log file deleted for IMPL_QUESTIONS.md. Re-run Phase 3. Do not log retry.

**If `DESIGN_QUESTIONS.md` exists** ([ARCH] tagged):
**Spawn** `architect`:
```
Read plans/[feature]/feedback/DESIGN_QUESTIONS.md.
Resolve each [ARCH] question — update ARCHITECTURE_PROPOSAL.md (or IMPLEMENTATION_PLAN.md for lite plans).
Delete plans/[feature]/feedback/DESIGN_QUESTIONS.md when resolved.
```
After resolved: log file deleted for DESIGN_QUESTIONS.md. Re-run Phase 3. Do not log retry.

Both files can exist simultaneously. Route one at a time using the priority order. After both resolve → builder re-implements.

---

## Transition to review

After Phase 3 completes with no blocking feedback files:
Compute wall_seconds: run `python -c "import time; print(int(time.time()) - BUILD_START)"` using `BUILD_START` from Phase 2.5.
Append `{"type": "AGENT_DONE", "agent": "builder", "model": "<model>", "conversation": <N>, "result": "DONE", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0, "tool_uses": 0, "wall_seconds": <computed>, "ts": "<iso-timestamp>"}` to EVENTS.jsonl.
Note: tokens/cost are 0 in Claude Code path; runner.py populates them when using `pathly-run` CLI.

Return. Orchestrator determines next state from transition_rules.
