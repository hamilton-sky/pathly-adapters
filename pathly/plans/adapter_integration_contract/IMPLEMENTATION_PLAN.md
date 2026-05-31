---
name: Implementation Plan
---
# Adapter Integration Contract — Implementation Plan

## Overview
This feature tightens the runtime contract between Pathly FSM responses and external adapters. The core work is in `fsm_ops.py`, where the response payloads are normalized and decision semantics are made explicit. The follow-up work updates the Codex-facing skill contract and tests so the new `agent_hint` surface is the primary integration path.

## Layer Architecture
The contract starts in the orchestrator, is rendered by adapter-facing docs, and is locked down by tests.

```
Plans (IMPLEMENTATION_PLAN.md)  →  FSM response shaping  →  Adapter docs + tests
         ↓                                 ↓                         ↓
  contract intent                 response schema + decisions      consumer alignment
```

## Phases

### Phase 1: Normalize FSM contract shape   ← Conversation: 1
**File:** `src/pathly_orchestrator/fsm_ops.py` — MODIFY: add `schema_version`, `decision`, `role`, `agent_hint`, `stage_brief`, and `warnings`; align the `next_action` and `complete_stage` payload shapes; keep a compatibility path for `codex_subagent` while the transition is in flight.
**Done when:** both FSM endpoints return the new contract fields and tests prove the adapter can read the same semantics from either response path.
**Delivers stories:** S1.1, S1.2
**Depends on:** existing FSM state recovery and current flow metadata.
**Enables:** adapter-facing docs to switch to `agent_hint` without guessing about shape differences.
**Details:**
- Keep the FSM as the source of truth for state, conv, and open feedback.
- Make `decision` explicit on both successful and non-successful completions.
- Bound `stage_brief` to structured, current-step context only.
- Preserve compatibility only long enough for the migration path to be safe.
**Verify:** `pytest -q tests/test_fsm_ops.py`

### Phase 2: Align Codex surface with the new hint contract   ← Conversation: 2
**File:** `src/pathly_data/adapters/codex/SKILL_EXECUTION.md` — MODIFY: replace the `codex_subagent` reading guidance with `agent_hint.role` and `agent_hint.instructions`, and describe the new decision-handling boundary.
**Done when:** the Codex adapter documentation points at `agent_hint` exclusively and the repo’s setup assertions no longer expect the legacy surface as the primary contract.
**Delivers stories:** S2.1, S2.2
**Depends on:** Phase 1 contract shape being present in the FSM.
**Enables:** Codex-side consumers and review docs to use the same adapter-agnostic surface.
**Details:**
- Keep the wording concise and implementation-facing.
- Explicitly document `continue` versus `block` versus `escalate`.
- Make it clear that `agent_hint.role` is the dispatch key and `agent_hint.instructions` is the prompt body.
**Verify:** `pytest -q tests/test_setup.py`

## Prerequisites
- Verify the live files listed in `FEATURE_INDEX.md` exist before editing.
- Confirm the FSM state machine already owns `state`, `conv`, and feedback recovery.

## Key Decisions
- The FSM remains the sole source of truth for session continuity.
- `decision` is the adapter’s control signal, not a local policy hint.
- `agent_hint` is the stable adapter-facing payload; `codex_subagent` is transitional only.
