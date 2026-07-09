---
name: Implementation Plan
---
# [Feature Name] — Implementation Plan

## Overview
[What this feature adds — which site, which actions, which workflow, 2-3 sentences]

## Layer Architecture
[Show how the feature spans the implementation layers]

```
Plans (IMPLEMENTATION_PLAN.md)  →  Implementation modules  →  Interfaces / contracts
         ↓                                  ↓                          ↓
[feature definition]              [business logic]            [public API / contracts]
```

## Phase 1: [Phase Title]
**File:** `src/path/to/file.ext` — [CREATE / MODIFY: what changes]
**Done when:** [one observable sentence — what is true when this phase is complete]
**Delivers stories:** S1.1, S1.2
**Depends on:** [prior phase, conversation, or "nothing"]
**Enables:** [next phase or acceptance criterion this unlocks]
**Details:**
[Specific implementation instructions — cfg list keys, method signatures, section names]
**Verify:** `<project verify command — e.g. pytest, make test>` ← standard/strict only; omit in lite

## Phase 2: [Phase Title] (estimated effort)
...

## Prerequisites
- [What must be true before starting]

## Key Decisions
- [Architecture decision 1 and rationale — e.g., which resolver keys to use]
- [Architecture decision 2 and rationale]
