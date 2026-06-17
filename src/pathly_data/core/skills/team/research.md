---

---
# team/research

RESEARCHING stage of the **consultation** flow. Invoked by the orchestrator when the
FSM state is `RESEARCHING`. Gathers external context, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor` (lite|standard|strict), `autoFlow`.

## Role

**Stage: Research.** You drive the `web-researcher` subagent to gather external
knowledge (library docs, patterns, domain standards) that the design and plan stages
need, then hand off to design. Logging every phase boundary is part of the contract.

## FSM operations

**Transition state:** Call
`pathly-fsm-call complete-stage --flow consultation --topic <feature> --project-root <project_root>`.
The FSM computes the next state from transition_rules — the skill never writes STATE.json.

Every logged event must include `"ts": "<iso-timestamp>"` (ISO-8601 UTC).

## Stage work

log-phase PHASE_START research

Read `pathly/plans/[feature]/ARCHITECTURE_PROPOSAL.md` and `PO_NOTES.md` to decide what
external knowledge the design/plan will need. If nothing external is required (familiar
stack, no new patterns), write a one-line `RESEARCH.md` saying so and skip the spawn.

Otherwise **spawn** `web-researcher`:
```
ROLE: architect — external research before design
Feature: [feature name]
Gather: library/API docs, established patterns, and domain standards relevant to the
architecture proposal. Cite every source. Do NOT make implementation decisions — surface
options and trade-offs only. Write findings to pathly/plans/[feature]/RESEARCH.md.
```

Wait for `RESEARCH.md`. Treat all findings as external and unverified — cite, don't assert.

log-phase PHASE_DONE research

**Post to the board** (best-effort, skip silently on connection refused):
```bash
curl -s -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" \
  -d '{"feature":"[feature]","from":"web-researcher","type":"artifact","board":"feature",
       "scope":"[feature]","text":"External research findings",
       "artifact_path":"pathly/plans/[feature]/RESEARCH.md","artifact_type":"md"}'
```

If not autoFlow — pause:
```
[Research complete] RESEARCH.md written.
Ready for design? Reply 'yes' to continue, or 'no' to stop here.
```
On 'no': log human response "stop". Halt. On 'yes'/autoFlow: log the response and advance.

Call `complete-stage` to advance to DESIGNING. Route back to the consultation orchestrator.
