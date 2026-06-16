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

Events are logged to the central DB via `pathly_orchestrator.eventlog.append_event`.
Every event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `pathly/plans/<feature>/STATE.json` by the FSM after each transition.

- **Log event:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type': 'FILE_CREATED', 'file': '<filename>', 'ts': '<iso-timestamp>'})"`
- **Log retry:** Same pattern with `{'type': 'RETRY', 'key': 'conv-N:FILE.md', 'ts': '<iso-timestamp>'}`.
- **Check retry count:** `python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Subagents (BUILDING stage)

| Action | Spawn |
|---|---|
| Implement | `builder` |
| Clarify requirement | `planner` |
| Clarify architecture | `architect` |

## Execution

log-phase PHASE_START build

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

log-phase PHASE_DONE build

Then run the Completion report with `agent: builder`, `result: DONE`, using `BUILD_START` from Phase 2.5.

Return. Orchestrator determines next state from transition_rules.
