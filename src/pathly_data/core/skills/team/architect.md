---

---
# team/architect

ARCHITECTING stage of the **consultation** flow. Invoked by the orchestrator when the
FSM state is `ARCHITECTING`. Produces the technical-design artifact, then advances.

Parse `$ARGUMENTS`: `FEATURE`, `rigor` (lite|standard|strict), `autoFlow`.

## Role

**Stage: Architecture.** You drive one subagent (the `architect`) to turn the
requirements into a technical design, then hand off to research. Logging every phase
boundary is part of the pipeline contract.

## FSM operations

**Transition state:** Call
`pathly-fsm-call complete-stage --flow consultation --topic <feature> --project-root <project_root>`.
The FSM computes the next state from transition_rules — the skill never writes STATE.json.

Every logged event must include `"ts": "<iso-timestamp>"` (ISO-8601 UTC).

## Stage work

log-phase PHASE_START architect

**Spawn** `architect` with `phase: storm`:
```
phase: storm
Feature: [feature name], rigor: [rigor]
Read <feature_path>/PO_NOTES.md as the authoritative requirements (if present).
Produce the technical design: layers touched, dependency direction, key decisions,
trade-offs, and risks. Write it to <feature_path>/ARCHITECTURE_PROPOSAL.md.
If a decision needs product input you cannot resolve, write an ARCH_QUESTION block to
<feature_path>/feedback/HUMAN_QUESTIONS.md and stop; otherwise finish the design.
```

Wait for `ARCHITECTURE_PROPOSAL.md` to be written.

log-phase PHASE_DONE architect

If not autoFlow — pause:
```
[Architecture complete] ARCHITECTURE_PROPOSAL.md written.
Ready for research? Reply 'yes' to continue, or 'no' to stop here.
```
On 'no': log human response "stop". Halt. On 'yes'/autoFlow: log the response and advance.

Call `complete-stage` to advance to RESEARCHING. Route back to the consultation orchestrator.
