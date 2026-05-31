---
name: Progress
---
# Adapter Integration Contract — Progress

## Status: NOT STARTED

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Normalize FSM response shape | Conv 1 | TODO |
| S1.2 | Separate block from escalate | Conv 1 | TODO |
| S2.1 | Expose adapter-agnostic hints | Conv 2 | TODO |
| S2.2 | Keep the contract bounded | Conv 2 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | Phase 1 | S1.1, S1.2 | TODO | `pytest -q tests/test_fsm_ops.py` |
| 2 | Phase 2 | S2.1, S2.2 | TODO | `pytest -q tests/test_setup.py` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Normalize FSM contract shape | `src/pathly_orchestrator/fsm_ops.py` | Add the new contract fields and align response shapes. | Both FSM endpoints expose the new contract semantics and tests pass. | TODO |
| 2 | Align Codex surface with the new hint contract | `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` | Replace legacy Codex hint wording with the `agent_hint` contract. | The Codex surface documentation uses the new fields and setup assertions are updated. | TODO |

## Prerequisites
- The FSM state for this feature must remain recoverable from disk state.

## Blocked By
- Nothing
