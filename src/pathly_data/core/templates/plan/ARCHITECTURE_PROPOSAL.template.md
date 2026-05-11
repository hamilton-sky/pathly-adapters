# [Feature Name] — Architecture Proposal

## Problem Statement
[What automation gap or framework capability are we adding?]

## Proposed Solution
[High-level description — new site, new action type, new resolver strategy, etc.]

## Layer Breakdown

```
Layer A   (plans/$ARGUMENTS — feature definition)
     │  "phase": "…"
     ▼
Layer B   (<module>/<component>/<file>.py)
     │  [orchestration / glue]
     ▼
Layer C   (<module>/<target>/<file>.py)
     │  [implementation / interaction]
     ▼
Runtime / framework
```

## Key Design Decisions

### Decision 1: [Title]
- **Options considered**: A, B, C
- **Chosen**: A
- **Rationale**: [Why A wins — e.g., label resolver is more resilient than CSS]

### Decision 2: [Title]
...

## Key Components
[What modules, classes, or functions are new — list each with a one-line description]

## Interface Design
[Public API and method signatures — what callers will depend on]

## Risks
- [Risk 1]: [Mitigation — e.g., site uses dynamic IDs → use role + label resolvers first]
- [Risk 2]: [Mitigation]
