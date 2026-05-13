# [Feature Name] — Mermaid Flow Diagram

## [Primary Flow Name, e.g. "Happy Path: setup workflow"]

```mermaid
flowchart TD
    A([Entry point / trigger]) --> B[Component / module]
    B --> C{Decision point?}
    C -- yes --> D[Next component]
    C -- no --> E[Alternate path]
    D --> F([Success outcome])
    E --> G([Outcome B])
```

## [Fallback / Error Flow]

```mermaid
flowchart TD
    A([Failure condition]) --> B[Error handler]
    B --> C{Recoverable?}
    C -- yes --> D([Retry / resume])
    C -- no --> E([Escalate / stop])
```

## Component Legend

| Node | Meaning |
|------|---------|
| `[Name]` | What this component does in this feature |
| `{Name}` | Decision point — branches on a condition |
| `([Name])` | Terminal node — entry point or final outcome |
| `...` | ... |
