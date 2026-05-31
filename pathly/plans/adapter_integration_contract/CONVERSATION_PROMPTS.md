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
- `src/pathly_orchestrator/fsm_ops.py` — add the new response contract fields and align the two endpoint payloads.
- `tests/test_fsm_ops.py` — update response-shape assertions and edge-case coverage for the new contract.

Scope:
- Normalize `next_action` and `complete_stage` around the same adapter-facing contract.
- Keep FSM state recovery authoritative.
- Preserve a compatibility transition path for `codex_subagent` only if needed for safe rollout.
- Make `decision` explicit and keep `stage_brief` bounded.

Architectural rules to observe:
- Read the live FSM and the current tests before editing.
- Stay within the orchestrator / contract layer. Do not touch adapter docs yet.

Do NOT touch `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` yet.
Verify: `pytest -q tests/test_fsm_ops.py`
After done, update pathly/plans/adapter_integration_contract/PROGRESS.md phases 1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** FSM endpoints emit the new contract fields consistently and the regression tests cover the new decision model.
**Files touched:** `src/pathly_orchestrator/fsm_ops.py`, `tests/test_fsm_ops.py`

---

## Conversation 2: Align Codex surface with the new hint contract (Phase 2)

**Stories delivered:** S2.1, S2.2

**Prompt to paste:**
```
Implement Adapter Integration Contract Conversation 2 (Phase 2) from pathly/plans/adapter_integration_contract/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` — replace legacy `codex_subagent` guidance with the new `agent_hint` contract.
- `tests/test_setup.py` — update setup/package assertions that still encode the old surface as primary.

Scope:
- Switch Codex-facing wording to `agent_hint.role` and `agent_hint.instructions`.
- Make the adapter boundary explicit for `continue`, `block`, and `escalate`.
- Keep the wording tight and implementation-facing.

Architectural rules to observe:
- Read the live docs and setup assertions before editing.
- Stay within the adapter surface and test surface. Do not reopen the FSM payload shape unless the tests prove it is required.

Do NOT touch `src/pathly_orchestrator/fsm_ops.py` yet.
Verify: `pytest -q tests/test_setup.py`
After done, update pathly/plans/adapter_integration_contract/PROGRESS.md phases 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report. If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Codex-facing instructions and setup assertions point at `agent_hint` and the contract boundaries are clear.
**Files touched:** `src/pathly_data/adapters/codex/SKILL_EXECUTION.md`, `tests/test_setup.py`
