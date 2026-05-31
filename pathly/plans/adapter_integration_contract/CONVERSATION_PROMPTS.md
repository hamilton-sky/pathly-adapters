---
name: Conversation Guide
---
# Adapter Integration Contract — Conversation Guide

Split into 2 conversations (max 4). Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Normalize FSM contract shape (Phase 1)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Implement Adapter Integration Contract Conversation 1 (Phase 1) from pathly/plans/adapter_integration_contract/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/fsm_ops.py` — apply the 5 targeted changes listed below.
- `tests/test_fsm_ops.py` — update response-shape assertions for all 5 changes.

**What is already done — do NOT re-implement:**
- `_response_envelope()` already returns `schema_version`, `decision`, `role`, `agent_hint`, `stage_brief`, `warnings`, `codex_subagent`, etc. Do not remove or rewrite the envelope — only make the 5 targeted changes below.

**5 changes to make (read IMPLEMENTATION_PLAN.md for details):**

1. **Rename `agent_hint` inner keys to adapter-neutral form.**
   Create a NEW `_agent_hint` function (separate from `_codex_subagent_hint`) that returns `{ agent, role, mode, instructions }` instead of `{ pathly_agent, codex_role, mode, instructions }`.
   `_response_envelope` uses the new `_agent_hint`.
   `codex_subagent` in the envelope uses the OLD `_codex_subagent_hint` (preserve it as a frozen legacy compat field — do NOT rename its inner keys).

2. **Fix `current_state` key consistency.**
   Remove the `current_state_key` parameter from `_response_envelope`.
   Always emit `"current_state"` regardless of which endpoint is calling the envelope.
   On `complete_stage`, pass the new state as `current_state_value=next_state`.

3. **Implement `escalate` as distinct from `block` in `_blocked_response`.**
   - `feedback["target_agent"] == "human"` → `decision = "escalate"`
   - `feedback["target_agent"]` is a non-human agent → `decision = "block"`
   - Gate failure with no routable feedback → `decision = "escalate"`
   Wrap `recover_state` calls in try/except and return an escalate envelope on JSON corruption.

4. **Normalize `_blocked_response` shape.**
   Refactor it to delegate to `_response_envelope` so blocked/escalated responses have `agent_hint`, `storage_path`, and the same top-level fields as normal responses.
   Add `file` to `warnings` as `{ "code": "open_feedback", "file": filename }`.
   Keep `blocked`, `target_agent`, `file` at top level for one-release compat.

5. **Update tests (`tests/test_fsm_ops.py`):**
   - Assert `agent_hint` has `role` and `agent` keys (not `codex_role`/`pathly_agent`).
   - Assert `codex_subagent` still has OLD keys (`codex_role`, `pathly_agent`).
   - Assert both endpoints emit `current_state` (not `next_state`).
   - Assert escalate triggers when target_agent is human.
   - Assert block triggers when target_agent is a non-human agent.
   - Assert blocked response contains `agent_hint` and `storage_path`.

Architectural rules:
- Stay within `fsm_ops.py` and `tests/test_fsm_ops.py`. Do not touch adapter docs or other modules.
- Read the live FSM and the current tests before editing.

Do NOT touch `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` yet.
Verify: `pytest -q tests/test_fsm_ops.py`
After done, update pathly/plans/adapter_integration_contract/PROGRESS.md Conv 1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** FSM endpoints emit the normalized contract, `agent_hint` uses adapter-neutral keys, `escalate` is distinct from `block`, both endpoints emit `current_state`, and tests pass.
**Files touched:** `src/pathly_orchestrator/fsm_ops.py`, `tests/test_fsm_ops.py`

---

## Conversation 2: Align Codex surface with the new hint contract (Phase 2)

**Stories delivered:** S2.1, S2.2

**Prompt to paste:**
```
Implement Adapter Integration Contract Conversation 2 (Phase 2) from pathly/plans/adapter_integration_contract/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` — add `## Decisions` block; verify `codex_subagent` is not taught as the primary read path.
- `tests/test_setup.py` — add/update assertions for the new Decisions block.

**What is already done — do NOT re-implement:**
- `SKILL_EXECUTION.md` already references `agent_hint.role` and `agent_hint.instructions`. Do not remove or rewrite those references.

**2 changes to make (read IMPLEMENTATION_PLAN.md for details):**

1. **Add `## Decisions` block** to `SKILL_EXECUTION.md` (after the current bullet list, before the CLI section):
   ```markdown
   ## Decisions

   Every FSM response includes a `decision` field:

   - `continue` — adapter may automate the next step without human involvement.
   - `block` — an agent-resolvable feedback file is open. Surface to the next
     Pathly agent via the standard feedback resolution flow.
   - `escalate` — human input is required (corrupt state, unknown feedback, or
     retry limit exceeded). Do not automate; surface to the user.
   ```

2. **Verify and fix `codex_subagent` as primary path.**
   Grep `SKILL_EXECUTION.md` for `codex_subagent`. If found as primary consumer guidance, replace with `agent_hint` references. The file should make clear that `agent_hint` is the primary contract and `codex_subagent` is legacy-only.

**Update tests (`tests/test_setup.py`):**
- Assert `SKILL_EXECUTION.md` contains the three decision values: `continue`, `block`, `escalate`.
- Assert `SKILL_EXECUTION.md` contains `agent_hint`.
- Assert `SKILL_EXECUTION.md` does NOT reference `codex_subagent` as the primary dispatch field (it may mention it only as legacy/compat).

Architectural rules:
- Read the live docs and setup assertions before editing.
- Stay within `SKILL_EXECUTION.md` and `tests/test_setup.py`. Do not reopen `fsm_ops.py`.

Do NOT touch `src/pathly_orchestrator/fsm_ops.py`.
Verify: `pytest -q tests/test_setup.py`
After done, update pathly/plans/adapter_integration_contract/PROGRESS.md Conv 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
```

**Expected output:** Codex-facing instructions document the three-value decision model (`continue`/`block`/`escalate`), `agent_hint` is the primary contract, and setup assertions reflect the new surface.
**Files touched:** `src/pathly_data/adapters/codex/SKILL_EXECUTION.md`, `tests/test_setup.py`
