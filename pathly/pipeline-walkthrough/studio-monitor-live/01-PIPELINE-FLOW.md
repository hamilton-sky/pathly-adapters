# studio-monitor-live — Pipeline Flow

**Branch:** master  
**Date:** 2026-05-25  
**User intent:** Studio Monitor live redesign — FSM rail, SSE badge, multi-flow tabs, running banner, last-used flow

---

## FSM State Sequence

→ STORMING  
→ PLANNING  
→ BUILDING  
→ REVIEWING  
→ BUILDING (Conv 2)  
→ REVIEWING  
→ TESTING  
→ DONE  

---

## Discovery & Storm

│  Orchestrator → STORMING (auto-advance)  
│  Orchestrator → PLANNING (auto-advance)  

---

## Build Traces

| Conv | Agent    | Model               | Result |
|------|----------|---------------------|--------|
| 1    | builder  | claude-sonnet-4-6   | DONE   |
| 2    | builder  | claude-sonnet-4-6   | DONE   |
| 2    | reviewer | claude-sonnet-4-6   | PASS   |
| 2    | tester   | claude-sonnet-4-6   | PASS   |

---

## Feedback Loops

| Stage | Retries | Cause | Resolution |
|-------|---------|-------|------------|
| —     | 0       | —     | —          |
