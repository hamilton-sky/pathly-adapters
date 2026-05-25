---
name: Flow Diagram
---
# studio-polish — Flow Diagram

## FlowEditor load state machine

```
[selectedItem changes]
        │
        ▼
  loading = true
  ┌─────────────┐
  │  SKELETON   │  ← shimmer animation, theme-aware colors
  └─────────────┘
        │
  readFile IPC resolves
        │
   ┌────┴────┐
   │         │
 success   error
   │         │
   ▼         ▼
jsYaml    loadError
.load()    state
   │
 ┌─┴──────────┐
 │            │
valid      YAMLException
   │            │
   ▼            ▼
flowData    parseError
 set        "line N: msg"
loading     loading
= false     = false
```

## Unsaved-changes navigation flow

```
User clicks sidebar item B
        │
        ▼
  currentItem dirty?
  ┌─────┴─────┐
  NO          YES
  │           │
  ▼           ▼
Switch     pendingNavigation = B
to B       Show confirm dialog
                │
         ┌──────┴──────┐
       Cancel        Discard
         │              │
         ▼              ▼
   pendingNav=null   clearDirty()
   stay on A         switch to B
```

## installer split

```
BEFORE:
  setup_command.py (523 lines)
    argparse + menu + _run_host + _run_host_uninstall +
    _codex_agent_toml + _codex_skill_openai_yaml + main()

AFTER:
  cli.py (~120 lines)
    argparse + menu + main()
    └─ calls orchestrate.run(args)

  orchestrate.py (~350 lines)
    _run_host + _run_host_uninstall + ALLOWED_HOSTS
    _codex_agent_toml + _codex_skill_openai_yaml

  setup_command.py (~5 lines)
    from .cli import main   ← backward-compat shim
```
