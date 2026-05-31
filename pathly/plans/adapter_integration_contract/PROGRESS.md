---
name: Progress
---
# Adapter Integration Contract — Progress

## Status: PLAN READY

Plan reviewed and updated by architect + web research on 2026-06-01.
Ready to build. Start with Conversation 1 prompt from CONVERSATION_PROMPTS.md.

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Normalize FSM response shape | Conv 1 | DONE |
| S1.2 | Separate block from escalate | Conv 1 | DONE |
| S2.1 | Expose adapter-agnostic hints | Conv 2 | DONE |
| S2.2 | Keep the contract bounded | Conv 2 | DONE |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | Phase 1 | S1.1, S1.2 | DONE | `pytest -q tests/test_fsm_ops.py` |
| 2 | Phase 2 | S2.1, S2.2 | DONE | `pytest -q tests/test_setup.py` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | Normalize FSM contract shape | `src/pathly_orchestrator/fsm_ops.py` | 4 targeted changes: (1) neutral `agent_hint` keys, (2) `current_state` on both endpoints, (3) `escalate` vs `block` decision, (4) normalize `_blocked_response` shape. | Both FSM endpoints expose the corrected contract and tests pass. | DONE |
| 2 | Align Codex surface with the new hint contract | `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` | Add `## Decisions` block; ensure `codex_subagent` is not taught as primary. | The Codex surface documents all three decision values and setup assertions are updated. | DONE |

## Prerequisites
- The FSM state for this feature must remain recoverable from disk state.
- `agent_hint` inner-key rename must NOT change `codex_subagent` — that field stays frozen with old keys.

## Blocked By
- Nothing
