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

## Phases

### Phase 1: [Phase Title] (estimated effort)
**Layer:** [API / Service / CLI / Data / UI / Infra]
**Delivers stories:** S1.1, S1.2
**Files:**
- `<module>/<component>/<file>.py` — [what changes]
- `<module>/<component>/<file>.py` — NEW: [what it does]

**Details:**
[Specific implementation instructions — cfg list keys, method signatures, action names]

**Verify:** `<project verify command — e.g. pytest, make test, or the stated verify script>`

### Phase 2: [Phase Title] (estimated effort)
...

## Prerequisites
- [What must be true before starting]

## Key Decisions
- [Architecture decision 1 and rationale — e.g., which resolver keys to use]
- [Architecture decision 2 and rationale]
