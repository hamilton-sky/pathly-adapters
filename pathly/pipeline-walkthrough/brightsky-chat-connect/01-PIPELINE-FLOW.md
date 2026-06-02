# Pipeline Flow — brightsky-chat-connect

**Date:** 2026-05-29
**Branch:** master
**User intent:** Connect Studio chat to Brightsky AI via WebSocket + OAuth

## Discovery / Storming
```
│  Orchestrator → PLANNING (skip-discovery / auto-advance)
│  Orchestrator → PLANNING (planner agent)
```

## Architect Consult
No architect agent spawned — planner handled design directly.

## Conversation Traces

### Conv 1 — Auth layer (S-01, S-02, S-03, S-08)
```
│  builder → DONE  (208s, 36 tool uses, $0.22)
│  RETRY: conv-1:REVIEW_FAILURES.md
│  builder → DONE  (110s, 22 tool uses, $0.15)  [review fix]
│  GATE_FAILED: require_artifact REVIEWING→TESTING
│  FEEDBACK_RESOLVED: HUMAN_QUESTIONS.md
│  Orchestrator → TESTING
│  Orchestrator → BUILDING  (Conv 2 not yet implemented — bounce back)
```

### Conv 2 — WebSocket client + UI wiring (S-04 through S-10)
```
│  builder → DONE  (192s, 26 tool uses, $0.28)
│  builder → DONE  (96s, 15 tool uses, $0.18)   [second pass]
│  Orchestrator → DONE
```

## Test Traces
No tester agent spawned. Testing was manual (checklist in CONVERSATION_PROMPTS.md).

## Feedback Loop Table

| Stage     | Retries | Cause                        | Resolution                        |
|-----------|---------|------------------------------|-----------------------------------|
| REVIEWING | 1       | REVIEW_FAILURES.md on Conv 1 | Builder fix pass (110s)           |
| TESTING   | 1       | GATE_FAILED: Conv 2 missing  | FSM bounced back to BUILDING      |

## FSM State Sequence
```
→ PLANNING
→ PLANNING
→ BUILDING
→ REVIEWING
→ TESTING
→ BUILDING
→ DONE
```
