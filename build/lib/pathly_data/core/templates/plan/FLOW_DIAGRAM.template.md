# [Feature Name] — Flow Diagram

## [Primary Flow Name, e.g. "Happy Path: setup workflow"]

```
[entry point / trigger]
        │
        ▼
[component / module]
        │  [key operation]
        ▼
[next component]
        │
        ├─ [success path] ──► [outcome A]
        └─ [failure path] ──► [outcome B]
```

## [Fallback / Error Flow]

```
[failure condition]
        │
        └─ [error handler]
                │
                └─ [recovery or escalation]
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| [Name] | What this component does in this feature |
| ...    | ...                                       |
