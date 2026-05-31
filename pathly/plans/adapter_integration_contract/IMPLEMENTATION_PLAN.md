---
name: Implementation Plan
---
# Adapter Integration Contract — Implementation Plan

## Overview
This feature tightens the runtime contract between Pathly FSM responses and external adapters.

Much of the envelope shape is **already present** in `fsm_ops.py` (`schema_version`, `decision`, `role`, `agent_hint`, `stage_brief`, `warnings`, `codex_subagent`). The remaining work is five targeted corrections to make the contract adapter-agnostic, consistent across both endpoints, and correct in its `block`/`escalate` semantics.

## Layer Architecture
```
Plans (IMPLEMENTATION_PLAN.md)  →  FSM response shaping  →  Adapter docs + tests
         ↓                                 ↓                         ↓
  contract intent                 response schema + decisions      consumer alignment
```

## What is already done (do NOT re-implement)
- `_response_envelope()` already returns `schema_version`, `decision`, `role`, `agent`, `agent_hint`, `stage_brief`, `warnings`, `menu`, `storage_path`, `codex_subagent`, `instructions`, `limits`.
- `codex_subagent` is already aliased to `agent_hint` as the compat field.
- `SKILL_EXECUTION.md` already references `agent_hint.role` and `agent_hint.instructions` on lines 9–12.

## Phases

### Phase 1: Normalize FSM contract shape   ← Conversation: 1
**File:** `src/pathly_orchestrator/fsm_ops.py`
**Done when:** both FSM endpoints return the same normalized shape, `agent_hint` is adapter-agnostic, `escalate` is a distinct decision, and tests pass.
**Delivers stories:** S1.1, S1.2
**Verify:** `pytest -q tests/test_fsm_ops.py`

#### Change 1 — Rename `agent_hint` inner keys to adapter-neutral form
Current `_codex_subagent_hint` returns `{ pathly_agent, codex_role, mode, instructions }`.
The `agent_hint` field exposed to adapters must instead return `{ agent, role, mode, instructions }`.

After the rename:
- `agent_hint.agent` = the Pathly role name (e.g., `"builder"`)
- `agent_hint.role` = the abstract dispatch label (`"worker"` or `"explorer"`)
- `agent_hint.instructions` = the full delegated prompt

**Keep `codex_subagent` as a frozen legacy snapshot** using the OLD keys (`codex_role`, `pathly_agent`) so existing Codex consumers are not broken during migration. Do NOT change `_codex_subagent_hint` itself — only create a new `_agent_hint` function that returns the neutral shape.

#### Change 2 — Make `current_state` canonical on both endpoints
`complete_stage` currently calls `_response_envelope(current_state_key="next_state", ...)`, which means `complete_stage` responses have a `next_state` key while `next_action` responses have `current_state`. Adapters must special-case which endpoint they called.

Fix: remove the `current_state_key` parameter from `_response_envelope`. Always emit `current_state`. On `complete_stage`, pass `current_state_value=next_state` so the field reflects the new state. Optionally add `"previous_state"` for traceability (low priority).

#### Change 3 — Implement `escalate` as distinct from `block`
`_blocked_response` currently always emits `"decision": "block"`. Semantics must be:
- `"block"` → agent-resolvable feedback file present; automated retry with an agent is appropriate.
- `"escalate"` → human-resolvable: target_agent is `"human"`, corrupt/unknown state, or retry limits exceeded.

Concretely:
- `feedback["target_agent"] == "human"` → `decision = "escalate"`
- `feedback["target_agent"]` is an agent → `decision = "block"`
- Gate failure with no routable feedback → `decision = "escalate"`
- Wrap `recover_state` in try/except → return an escalate envelope on JSON corruption

#### Change 4 — Normalize `_blocked_response` shape to match the envelope
`_blocked_response` currently returns a different shape (missing `agent_hint`, `storage_path`). Refactor it to delegate to `_response_envelope` so blocked/escalated responses have the same top-level fields. Move `file` into `warnings` as a structured entry `{ "code": "open_feedback", "file": filename }`. Keep `blocked`, `target_agent`, `file` as top-level legacy compat fields for one release.

#### Change 5 — Update tests
`tests/test_fsm_ops.py` must assert:
- `agent_hint` has `role` and `agent` keys (not `codex_role` / `pathly_agent`)
- `codex_subagent` still has the OLD keys (`codex_role`, `pathly_agent`) for compat
- Both endpoints emit `current_state` (not `next_state`)
- Escalate decision triggers when target is human
- Block decision triggers when target is an agent
- Blocked response contains `agent_hint` and `storage_path`

---

### Phase 2: Align Codex surface with the new hint contract   ← Conversation: 2
**File:** `src/pathly_data/adapters/codex/SKILL_EXECUTION.md`
**Done when:** the Codex adapter documentation explicitly documents the three-value decision model and no longer teaches `codex_subagent` as the primary read path.
**Delivers stories:** S2.1, S2.2
**Depends on:** Phase 1 contract shape being present in the FSM.
**Verify:** `pytest -q tests/test_setup.py`

#### Change 1 — Add a `## Decisions` block
Insert between the current bullet list and the CLI section:

```markdown
## Decisions

Every FSM response includes a `decision` field:

- `continue` — adapter may automate the next step without human involvement.
- `block` — an agent-resolvable feedback file is open. Surface to the next
  Pathly agent via the standard feedback resolution flow.
- `escalate` — human input is required (corrupt state, unknown feedback, or
  retry limit exceeded). Do not automate; surface to the user.
```

#### Change 2 — Ensure `codex_subagent` is not taught as primary
Verify with grep that the file does NOT present `codex_subagent` as the primary consumer path. If found, replace with guidance that directs consumers to `agent_hint`.

**Update tests:** `tests/test_setup.py` should assert that SKILL_EXECUTION.md mentions `agent_hint` and the three decision values, and does NOT reference `codex_subagent` as the primary dispatch field.

---

## Prerequisites
- Verify the live files listed in `FEATURE_INDEX.md` exist before editing.
- Confirm `_codex_subagent_hint` returns `codex_role` and `pathly_agent` (it does — preserve this for `codex_subagent` compat).

## Key Decisions
- The FSM remains the sole source of truth for session continuity.
- `decision` is the adapter's control signal: `continue | block | escalate`.
- `agent_hint` is the stable adapter-facing payload with neutral key names.
- `codex_subagent` is frozen legacy with the old key names; do not update its inner shape.
- `block` = agent-resolvable (retry with a Pathly agent). `escalate` = human-resolvable.
