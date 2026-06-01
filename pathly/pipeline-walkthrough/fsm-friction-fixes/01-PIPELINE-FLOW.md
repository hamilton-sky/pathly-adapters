# fsm-friction-fixes — Pipeline Flow

**Date:** 2026-06-01
**Branch:** master
**User intent:** fix the three FSM friction points: auto-start server, file-touch scope gate, multi-conversation routing

## FSM State Sequence

→ PLANNING
→ DESIGNING
→ BUILDING
→ REVIEWING
→ BUILDING
→ REVIEWING
→ BUILDING
→ REVIEWING
→ TESTING
→ RETRO

## Discovery / Storm Trace

│  Orchestrator → STORMING → PLANNING (auto-advance from storm seed)
│  team/discover → PLANNING (completed, cost $0.42)

## Architect Consult Trace

(No separate architect spawn — planning was done via team/discover)

## Conversation Traces

| Conv | Agent       | Tokens | Cost    | Wall   | Result |
|------|-------------|--------|---------|--------|--------|
| 1    | builder     | n/c    | n/c     | n/c    | DONE   |
| 1    | reviewer    | 47,921 | $0.259  | 86s    | PASS   |
| 2    | builder     | n/c    | n/c     | n/c    | DONE   |
| 2    | reviewer    | 32,968 | $0.178  | 480s   | PASS   |
| 3    | builder     | n/c    | n/c     | n/c    | DONE   |
| 3    | reviewer    | 47,126 | $0.254  | 121s   | PASS   |

## Test Traces

| Agent  | Conv | Tokens | Cost   | Wall  | Result |
|--------|------|--------|--------|-------|--------|
| tester | 0    | 67,070 | $0.362 | 344s  | PASS   |

## Feedback Loop Table

| Stage     | N | Cause                                    | Resolution                                    |
|-----------|---|------------------------------------------|-----------------------------------------------|
| REVIEWING | 1 | Missing GATE_DEGRADED test (Conv 2)      | Added test_scope_gate_degraded_truncated_baseline |
| REVIEWING | 1 | _count_planned_convs regex overcounting (Conv 3) | Rewrote to anchored re.match + unique set |
