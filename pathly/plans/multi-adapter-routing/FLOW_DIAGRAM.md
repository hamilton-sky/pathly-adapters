---
name: Flow Diagram
---
# Multi-Adapter Routing — Flow Diagram

## Happy Path: routed stage dispatch

```
flow YAML (adapter_map)
        │  read by FSM
        ▼
/next_action  (fsm_ops.py)
        │  _resolve_adapter(flow, state)
        ▼
preferred_adapter = "codex"
        │  returned in response
        ▼
pathly-dispatch
        │  pref == current adapter?
        ├─ yes / "" ──► run agent_hint.instructions in place
        └─ no ───────► emit handoff packet:
                          { target=codex, storage_path, instructions (verbatim) }
                              │
                              └─► user/host pastes into codex ──► builder runs there
```

## Resolution precedence (inside _resolve_adapter)

```
[1] per-feature override (STATE.json)   ← reserved, NOT implemented now
        │ (skip)
        ▼
[2] adapter_map[current_state] ?  ──yes──► use it
        │ no
        ▼
[3] adapter_map["default"] present? ──yes──► use it
        │ no
        ▼
[4] ""   (no adapter_map → backward compatible)
```

## Validation Flow (state.py)

```
flow has adapter_map?
        │ no ──► valid (backward compatible)
        │ yes
        ▼
default key present? ──no──► FAIL "missing default"
        │ yes
        ▼
every value in {claude,codex,copilot}? ──no──► FAIL "unknown adapter: X"
        │ yes
        ▼
every per-state key is a declared state? ──no──► FAIL "unknown state: Y"
        │ yes
        ▼
valid
```

## Anti-drift loop (TS ↔ Python)

```
Studio generateYaml() ──emits──► adapter_map block
        │
        ▼
round-trip test ──feeds──► validate_flow_cli (the single arbiter)
        │
        ├─ passes ──► shapes agree
        └─ fails  ──► CI red (Studio must conform to the validator)
```

## Component Legend

| Symbol | Meaning |
|--------|---------|
| `_resolve_adapter` | Pure helper in fsm_ops.py mapping (flow, state) → preferred_adapter |
| `preferred_adapter` | New string field in the /next_action response; "" when unset |
| handoff packet | target adapter + storage_path + verbatim instructions emitted by dispatch |
| validate_flow_cli | Flow YAML validator in state.py — single arbiter of adapter_map shape |
| round-trip test | Asserts wizard YAML passes the validator — prevents TS/Python drift |
