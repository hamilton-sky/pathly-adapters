# agent-architecture-refactor — Flow Diagram

## Before: scout-path indirection

```
skill (build.md / test.md / review.md)
  │
  ├── Phase 1: Analyze
  │     spawn agent with phase:analyze
  │     → NEEDS_CONTEXT block returned
  │
  ├── Phase 2: Scout
  │     Call `scout-path` with NEEDS_CONTEXT + ROLE + FEATURE
  │       scout-path.md loaded into context
  │       └── scout-path spawns scout/quick agents (parallel)
  │             └── findings compressed by scout-path
  │             └── compressed summary returned to skill
  │
  └── Phase 3: Main phase
        ## Scout Findings injected
        spawn agent with phase:build/review/test
```

## After: direct spawn

```
skill (build.md / test.md / review.md)
  │
  ├── Phase 1: Analyze
  │     spawn agent with phase:analyze
  │     → NEEDS_CONTEXT block returned
  │
  ├── Phase 2: Scout (inline)
  │     skill reads NEEDS_CONTEXT
  │     spawns scout/quick agents directly (parallel, max 4)
  │     compresses findings inline
  │
  └── Phase 3: Main phase
        ## Scout Findings injected
        spawn agent with phase:build/review/test
```

---

## team.md: before (monolithic) vs. after (thin launcher)

```
BEFORE — team.md (monolithic, single context window)
┌─────────────────────────────────────────────────────────┐
│ arg parsing → feature detect → mode select              │
│   │                                                     │
│   ├── [nano] → builder → reviewer → done                │
│   │                                                     │
│   └── [normal] → FSM recovery → routing loop           │
│         ├── IDLE → team/discover                        │
│         ├── PLANNING → team/plan                        │
│         ├── BUILDING → team/build                       │
│         │     └── [autoFlow] git commit                 │
│         ├── REVIEWING → team/review                     │
│         │     └── [pass] PROGRESS.md update + commit    │
│         ├── TESTING → team/test                         │
│         └── DONE → stop                                 │
└─────────────────────────────────────────────────────────┘

AFTER — team.md (thin launcher) + orchestrator agent
┌───────────────────────────────┐     ┌──────────────────────────────────┐
│ team.md                       │     │ orchestrator agent               │
│                               │     │                                  │
│ arg parsing                   │     │ FSM recovery (STATE.json / EVENTS)│
│ feature detect                │     │ routing loop                     │
│ mode select                   │     │   IDLE → team/discover           │
│   │                           │     │   PLANNING → team/plan           │
│   ├── [nano] inline → done    │     │   BUILDING → team/build          │
│   │                           │     │     └── [autoFlow] git commit    │
│   └── spawn orchestrator ─────┼────►│   REVIEWING → team/review        │
│         FEATURE, rigor,       │     │     └── [pass] PROGRESS.md + commit│
│         autoFlow, entryStage  │     │   TESTING → team/test            │
│                               │     │   DONE → stop                    │
└───────────────────────────────┘     └──────────────────────────────────┘
```

---

## Tester agent: before vs. after

```
BEFORE — tester.md
  phase:analyze → NEEDS_CONTEXT (no spawn authority for scout/quick)
  phase:test    → verify criteria

AFTER — tester.md
  phase:analyze → NEEDS_CONTEXT (same, unchanged)
  [delegation section] → can spawn scout (multi-file) or quick (single-file)
  phase:test    → verify criteria (same, unchanged)

tester.yaml: can_spawn: [builder]  →  can_spawn: [quick, scout, builder]
```
