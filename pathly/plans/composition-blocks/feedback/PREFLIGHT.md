# composition-blocks — Pre-flight Baseline

_Recorded: 2026-06-03_

---

## 1. Test Baseline

```
python -m pytest tests/ -q
382 passed, 3 skipped in 22.39s
```

No pre-existing failures.

---

## 2. TypeScript Baseline

```
cd studio && npx tsc --noEmit -p tsconfig.web.json
```

Clean — no pre-existing type errors.

Note: `node_modules/.bin/tsc` is not on PATH from repo root; correct invocation is `cd studio && npx tsc ...`.

---

## 3. Path Confirmations

| Path | Exists |
|---|---|
| `src/pathly_data/core/skills/composition.yaml` | ✓ |
| `src/pathly_orchestrator/compose.py` | ✓ |
| `src/pathly_orchestrator/state.py` | ✓ |
| `src/pathly_orchestrator/fsm_ops.py` | ✓ |
| `tests/test_compose.py` | ✓ |
| `studio/src/renderer/src/components/FlowWizard/FlowWizard.tsx` | ✓ |
| `studio/src/renderer/src/components/FlowWizard/types.ts` | ✓ |

---

## 4. Flow/State Validator Test File

`tests/test_state*.py` — **does not exist**.

The flow validator tests live in **`tests/test_transition_actions.py`**.
- Tests `validate_flow_cli()` from `pathly_orchestrator.state`
- Includes `adapter_map` validation tests starting at line 130
- Conv 2 should add `composition:` key tests to this file.

---

## 5. `state.py` — Key Line Ranges

### Allowed top-level keys collection

**`_REQUIRED_FLOW_KEYS`** — lines 48–54:
```python
_REQUIRED_FLOW_KEYS = {
    "storage_path",
    "states",
    "transitions",
    "agent_map",
    "feedback_routing",
}
```

**`_KNOWN_OPTIONAL_FLOW_KEYS`** — lines 55–61:
```python
_KNOWN_OPTIONAL_FLOW_KEYS = {
    "transition_rules",
    "version",
    "flow",
    "transition_actions",
    "adapter_map",
}
```

Conv 2 must add `"composition"` to `_KNOWN_OPTIONAL_FLOW_KEYS` (line ~61).

### `adapter_map` validation block — lines 148–162

```python
# adapter_map validation (optional field — omitting it is fully backward compatible)
if "adapter_map" in flow:
    adapter_map = flow["adapter_map"] or {}
    if "default" not in adapter_map:
        errors.append("adapter_map: 'default' key is required")
    declared_states = set(flow.get("states") or [])
    for key, value in adapter_map.items():
        if value not in _KNOWN_ADAPTERS:
            errors.append(...)
        if key != "default" and key not in declared_states:
            errors.append(...)
```

Conv 2 validation block for `composition:` should follow this exact pattern (after line 162).

---

## 6. `fsm_ops.py` — `build_prompt` and `compose_skill` Call Site

**`build_prompt` function** — line 101:
```python
def build_prompt(flow_config: dict, state_name: str, storage_path: Path) -> str:
```

**`compose_skill` import** — line 106 (lazy, inside the function):
```python
from pathly_orchestrator.compose import compose_skill
```

**`compose_skill` call site** — line 109:
```python
agent_text = compose_skill(agent, adapter)
```

**How active flow yaml is accessed:** `flow_config` is a pre-parsed dict passed as a parameter. It is loaded earlier via `_load_flow(flow_name)` (line 68) and passed down to `build_prompt`. The `composition:` key would be accessed as `flow_config.get("composition", {})`.

Conv 2 modification target: replace line 109 — when `flow_config` has a `composition:` key and the current `state_name` is in it, call `compose_skill_with_block(agent, block_name, adapter)` instead.
