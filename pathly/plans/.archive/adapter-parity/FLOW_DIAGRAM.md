---
name: Flow Diagram
---
# adapter-parity — Flow Diagram

## Adapter content pipeline

```
src/pathly_data/core/
  agents/
    explorer.md  ← NEW behavioral contract
    scout.md
    builder.md
    ...

  skills/
    archive/SKILL.md    ← existing
    commit/SKILL.md     ← existing

src/pathly_data/adapters/
  claude/_meta/
    archive_skill.yaml        ← existing (source of truth)
    archive-artifacts_skill.yaml
    commit_skill.yaml

  copilot/_meta/
    archive_skill.yaml        ← NEW (copy from claude)
    archive-artifacts_skill.yaml  ← NEW
    commit_skill.yaml         ← NEW
    install.yaml              ← MODIFY (remove hooks:)
    explorer.yaml             ← existing (backed by explorer.md)

  codex/_meta/
    commit_skill.yaml         ← NEW (copy from claude)
    explorer.yaml             ← existing (backed by explorer.md)
```

## Focus ring token resolution

```
[data-theme="dark"] (default)
  --focus-ring = 2px solid #38BDF8 (sky blue)
  
[data-theme="paper"]
  --focus-ring = 2px solid #c75c2a (warm orange)

component:focus-visible
  outline: var(--focus-ring)   ← resolves to correct color per theme
  
Before fix:
  outline: 2px solid #89b4fa  ← ALWAYS Mocha blue regardless of theme
```
