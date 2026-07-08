# team/build

Stage 3a — Implement. Invoked by the `team` orchestrator when FSM state is BUILDING.
Executes ONE work item (**analyze → scout → implement**), then transitions to REVIEWING.

Parse `$ARGUMENTS`: `FEATURE`, `rigor`, `autoFlow`.

> Shared protocols — **Scout choreography**, **Feedback protocol**, **Completion report**,
> **Sub-agent spawning rules**, and **Live progress logging** — are composed in below from
> fragments. This body covers only the BUILDING-stage specifics.

## Role

**Stage orchestrator: Building**
You coordinate subagents, handle feedback routing, and log every phase boundary.
Logging is mandatory — each `log-phase` call is part of the pipeline contract.

The phase shape is the **same as review/test**: a work item is selected, then the builder
runs `analyze → scout → implement`. Analyze and scout are **never skipped** — they are how the
builder discovers the architectural rules and conventions (CLAUDE.md, `.claude/rules/`,
ARCHITECTURE_PROPOSAL.md) that the task text does not carry. Skipping them ships blind.

> After each phase completes, log `log-phase PHASE_DONE <phase>` before starting the next.
> If `pathly-fsm-call` is unavailable, skip silently — never block execution.

## FSM operations

Events are logged to the central DB via `pathly_orchestrator.eventlog.append_event`.
Every event must include `"ts": "<iso-timestamp>"` using the current ISO-8601 UTC time.
State snapshots are written to `<feature_path>/STATE.json` by the FSM after each transition.

- **Log event:** `python3 -c "from pathly_orchestrator.eventlog import append_event; append_event('<feature_path>', {'type': 'FILE_CREATED', 'file': '<filename>', 'ts': '<iso-timestamp>'})"`
- **Log retry:** Same pattern with `{'type': 'RETRY', 'key': 'conv-N:FILE.md', 'ts': '<iso-timestamp>'}`.
- **Check retry count:** `python3 -c "from pathly_orchestrator.db import get_db; c=get_db(); print(c.execute(\"SELECT COUNT(*) FROM fsm_events WHERE feature=? AND event_type='RETRY' AND json_extract(payload,'$.key')=?\",('<feature>','conv-N:FILE.md')).fetchone()[0])"`
- **Never** append `STATE_TRANSITION` events — the FSM writes all state transitions after your AGENT_DONE.

## Subagents (BUILDING stage)

| Action | Spawn |
|---|---|
| Phase 1 — Analyze needs | `builder` (phase: analyze) |
| Phase 2 — Scout context | `scout` or `quick` with `ROLE: builder` |
| Phase 3 — Implement | `builder` (phase: implement) |
| Clarify requirement | `planner` |
| Clarify architecture | `architect` |

## Execution

log-phase PHASE_START build

## Phase 0 — Select the work item

Determine the ONE thing to build this stage. The **board task DAG is authoritative**; the
conversation table is a fallback for older plans that have no DAG.

### Board task DAG (preferred)

```
curl -s "http://127.0.0.1:8765/comms/tasks?ready=true&feature=[feature]&scope=[feature]"
```
**If the response is a non-empty list of ready tasks, BUILD FROM THE BOARD** — the DAG is the
authoritative work list (it supersedes PROGRESS.md / CONVERSATION_PROMPTS.md). Build **exactly
ONE task this stage**, then hand off to review. The FSM runs one build→review cycle **per task**:
after the reviewer passes it loops back to BUILDING for the next ready task, and only once the
whole DAG is drained does it advance to a single TESTING pass. Do **not** drain the rest of the
DAG here.

1. Pick ONE ready task. Claim it: `POST /comms/tasks/claim {"message_id":"<id>","run_id":"build"}`.
   If `claimed` is false, another worker took it — re-fetch and pick another.
2. This task is the **work item**. Its `text` is a self-contained builder prompt (what to build ·
   Files · Done when) and its `artifact_path` points at plan context. Note `WORK_ITEM = "board task <id>"`.
3. If `feedback/INCOMPLETE_TASKS.md` exists (the completeness gate sent you back to finish the
   DAG), `rm` it after completing this task — the gate re-checks the DAG on the next transition
   and re-raises it if work still remains.

Proceed to Phase 1 with this task as the work item.

### Conversation fallback (no board DAG — older plans)

If the response is empty OR the server is unreachable (connection refused), read
`<feature_path>/PROGRESS.md`. Find the first conversation row with status TODO. This is Conv N —
the **work item**. Note `WORK_ITEM = "conversation N"`. Do NOT update PROGRESS.md — the
orchestrator marks it DONE after the reviewer passes.

## Phase 1 — Analyze

log-phase PHASE_START analyze

**Spawn** `builder` with `phase: analyze` (see Scout choreography for the NEEDS_CONTEXT contract):
```
phase: analyze
Work item for [feature]: <WORK_ITEM>.
  - Board task: read the task text and its artifact_path for what to build.
  - Conversation N: route to continue [feature] conversation N.
List what you need to know before implementing — output NEEDS_CONTEXT block only.

Always include at minimum:
  - type: scout | scope: CLAUDE.md, .claude/rules/, <feature_path>/ARCHITECTURE_PROPOSAL.md | question: what architectural rules, doc-sync obligations, and coding conventions apply to the files this work item touches?
```

log-phase PHASE_DONE analyze

## Phase 2 — Scout

log-phase PHASE_START scout

Run the Scout choreography with `ROLE: builder`. Always run at least the default rules scout
above (CLAUDE.md / `.claude/rules/` / ARCHITECTURE_PROPOSAL.md) so the builder implements against
the same conventions the reviewer will check. Use the returned compressed summary as Scout Findings.

log-phase PHASE_DONE scout

## Phase 2.5 — Record build start time

Run: `python -c "import time; print(int(time.time()))"` and note the printed integer as `BUILD_START`.

## Phase 3 — Implement

log-phase PHASE_START implement

**Spawn** `builder` with `phase: implement`:
```
phase: implement
Implement the work item for [feature]: <WORK_ITEM>.
  - Board task: execute exactly this task; read its artifact_path for plan context.
  - Conversation N: execute conversation N only, in manual mode.
Verify. Do NOT update PROGRESS.md — the orchestrator handles that after the reviewer passes.

## Scout Findings
[compressed summary from Phase 2]

If you hit requirement ambiguity (what should this do?): write <feature_path>/feedback/IMPL_QUESTIONS.md
If you hit a technical blocker (how is this possible?): write <feature_path>/feedback/DESIGN_QUESTIONS.md
Use the shared feedback protocol formats, then report blocked.
Report: files changed, verify result, stories delivered.
```

**On a board task**, after the builder reports success, close it:
`POST /comms/tasks/complete {"message_id":"<id>","feature":"[feature]"}`.
On unrecoverable failure: `POST /comms/tasks/fail {"message_id":"<id>","reason":"<short>"}`.

log-phase PHASE_DONE implement

### Feedback routing after builder

Feedback file priority, the feedback-open guard, and the retry-count guard are defined in the
Feedback protocol fragment. Route the highest-priority open file to the agent below.

**If `IMPL_QUESTIONS.md` exists** ([REQ] tagged):
**Spawn** `planner`:
```
Read <feature_path>/feedback/IMPL_QUESTIONS.md.
Answer each [REQ] question — clarify in USER_STORIES.md or CONVERSATION_PROMPTS.md.
Delete <feature_path>/feedback/IMPL_QUESTIONS.md when resolved.
```
After resolved: log file deleted for IMPL_QUESTIONS.md. Re-run Phase 3. Do not log retry.

**If `DESIGN_QUESTIONS.md` exists** ([ARCH] tagged):
**Spawn** `architect`:
```
Read <feature_path>/feedback/DESIGN_QUESTIONS.md.
Resolve each [ARCH] question — update ARCHITECTURE_PROPOSAL.md (or IMPLEMENTATION_PLAN.md for lite plans).
Delete <feature_path>/feedback/DESIGN_QUESTIONS.md when resolved.
```
After resolved: log file deleted for DESIGN_QUESTIONS.md. Re-run Phase 3. Do not log retry.

Both files can exist simultaneously. Route one at a time using the priority order. After both resolve → builder re-implements.

## Transition to review

After Phase 3 completes with no blocking feedback files:

### Phase 3.5 — Write VERIFY.md

Write `<feature_path>/VERIFY.md` with this exact content (first line must be exact):
```
RESULT: PASS
Verified: <work item> complete — <one-sentence summary of what was verified and the outcome>
```

The first line **must** be `RESULT: PASS` verbatim (case-sensitive, no leading whitespace).

log-phase PHASE_DONE build

Then run the Completion report with `agent: builder`, `result: DONE`, using `BUILD_START` from Phase 2.5.

Return. Orchestrator determines next state from transition_rules.
