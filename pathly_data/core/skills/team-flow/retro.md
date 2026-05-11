# team-flow/retro

Stage 5 — Retrospective. Invoked by the `team-flow` orchestrator when FSM state is RETRO.

Parse `$ARGUMENTS`: `FEATURE`.

## FSM operations

- **Transition state to X:** Write `plans/<feature>/STATE.json` `{"current": "X"}`.
  Append `{"type": "STATE_TRANSITION", "to": "X"}` to `plans/<feature>/EVENTS.jsonl`.

## Subagents

| Action | Spawn |
|---|---|
| Run retrospective | `quick` |

---

**Spawn** `quick`:
```
Route to retro [feature].
Ask the 3 retrospective questions and return the RETRO.md-ready summary.
Do not write files; quick is read-only. The retro skill/orchestrator writes RETRO.md.
```

After quick completes:
- Write `plans/[feature]/RETRO.md` with the summary provided.
- Append any extracted lessons to `LESSONS_CANDIDATE.md` (project root or plans/).
- Append `{"type": "AGENT_DONE", "agent": "quick"}` to EVENTS.jsonl.
- Transition state → DONE.

Print:
```
[Stage 5 — Retro complete]
Pipeline complete. RETRO.md written to plans/[feature]/.
Lessons appended to LESSONS_CANDIDATE.md (if any were extracted).
Feature '[feature]' is DONE.

To promote lessons to active memory: route to lessons
```

Route back to `team-flow [FEATURE]`. (Orchestrator reads state DONE and stops.)
