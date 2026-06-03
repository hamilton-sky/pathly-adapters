# team/build

Stage 3a — Implement. Invoked by the `team` orchestrator when FSM state is BUILDING.
Executes one TODO conversation (analyze → scout → implement), then transitions to REVIEWING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the BUILDING-stage specifics.

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

**Spawn** `builder` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Route to continue [feature] conversation N.
List what you need to know before implementing — output NEEDS_CONTEXT block only.
```

### Phase 2 — Scout

Run the Scout choreography with `ROLE: builder`. Use the returned compressed summary as Scout Findings.

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

If you hit requirement ambiguity (what should this do?): write pathly/plans/[feature]/feedback/IMPL_QUESTIONS.md
If you hit a technical blocker (how is this possible?): write pathly/plans/[feature]/feedback/DESIGN_QUESTIONS.md
Use the shared feedback protocol formats, then report blocked.
Report: files changed, verify result, stories delivered.
```

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
