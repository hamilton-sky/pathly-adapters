# TEST REPORT — adapter_integration_contract Conv 1

**Date:** 2026-06-01
**Test run:** `pytest -q tests/test_fsm_ops.py -v`
**Result:** 18 passed, 0 failed

---

## Story 1.1: Normalize FSM response shape

```
Story 1.1: Normalize FSM response shape

  Criterion: Both next_action and complete_stage return current_state at the top level (never next_state)
  Test: test_current_state_key_on_next_action, test_current_state_key_on_complete_stage
        (also asserted in test_next_action_initial_state, test_complete_stage_after_planning,
        test_complete_stage_with_valid_decision, test_complete_stage_blocked_by_review_failures)
  Status: PASS

  Criterion: agent_hint has adapter-neutral keys: agent, role, mode, instructions
  Test: test_agent_hint_uses_neutral_keys (verifies agent, role, absence of codex_role/pathly_agent);
        test_next_action_includes_codex_worker_hint (verifies agent + role values);
        test_next_action_initial_state (verifies agent and role keys present)
  Status: PASS
  Notes: mode key is present in implementation (fsm_ops.py:139,160,329) but no test asserts its
         presence in agent_hint. The criterion is satisfied at the implementation level; test
         coverage for the mode key specifically is a minor gap but does not cause a failure.

  Criterion: codex_subagent retains legacy keys: codex_role, pathly_agent, mode, instructions
  Test: test_codex_subagent_retains_legacy_keys, test_next_action_includes_codex_worker_hint,
        test_complete_stage_blocked_by_review_failures
  Status: PASS
  Notes: Tests verify codex_role and pathly_agent. mode is not separately asserted in tests
         but is present in implementation.

  Criterion: Blocked/escalated responses include agent_hint, storage_path, and stage_brief
  Test: test_blocked_response_has_agent_hint_and_storage_path (agent_hint + storage_path on block),
        test_complete_stage_blocked_by_review_failures (agent_hint + storage_path + stage_brief on block),
        test_next_action_corrupt_state_escalate_has_storage_path (storage_path on escalate)
  Status: PASS
  Notes: stage_brief on escalated (corrupt state) response is not explicitly asserted in the
         escalate test, but the implementation sets it (fsm_ops.py:330,424). The blocked path is
         fully covered. The escalate path is partially covered (storage_path asserted, stage_brief
         not asserted).
```

---

## Story 1.2: Separate block from escalate

```
Story 1.2: Separate block from escalate

  Criterion: Agent-target feedback -> decision = "block"
  Test: test_block_decision_when_target_is_non_human_agent,
        test_complete_stage_blocked_by_review_failures,
        test_blocked_response_has_agent_hint_and_storage_path,
        test_blocked_response_warnings_contain_open_feedback
  Status: PASS

  Criterion: Human-target feedback -> decision = "escalate"
  Test: test_escalate_decision_when_target_is_human
  Status: PASS

  Criterion: Corrupt state (recover_state failure) -> decision = "escalate" AND response includes storage_path
  Test: test_next_action_corrupt_state_escalate_has_storage_path
  Status: PASS

  Criterion: Gate failure with no routable feedback -> decision = "escalate"
  Test: (none found)
  Status: NOT COVERED
  Notes: No test exercises the path where complete_stage encounters a gate failure with no
         feedback file present. This criterion is from S1.2 in USER_STORIES.md. Implementation
         behavior for this path is unverified by tests.

  Criterion: The adapter can safely automate continue and block, but must surface escalate to the user
  Test: (none found — this is a documentation/contract criterion, not directly testable at the
        unit level, but no integration test or contract test covers it either)
  Status: NOT COVERED
  Notes: This is a behavioral contract statement. No test verifies that escalate responses are
         structured in a way that forces surfacing (e.g., assert no auto-retry field, or that
         escalate does not carry the same continue-able shape). Low risk given the decision
         enum is already verified, but the specific adapter safeguard is untested.
```

---

## Summary

| Criterion | Status |
|---|---|
| S1.1 — current_state key on both endpoints | PASS |
| S1.1 — agent_hint neutral keys | PASS |
| S1.1 — codex_subagent legacy keys | PASS |
| S1.1 — blocked/escalated have agent_hint + storage_path + stage_brief | PASS |
| S1.2 — agent-target feedback -> block | PASS |
| S1.2 — human-target feedback -> escalate | PASS |
| S1.2 — corrupt state -> escalate + storage_path | PASS |
| S1.2 — gate failure no feedback -> escalate | NOT COVERED |
| S1.2 — adapter must surface escalate (contract safeguard) | NOT COVERED |

**Overall: 7 PASS / 2 NOT COVERED / 0 FAIL**

The two NOT COVERED items are coverage gaps, not failures. No test failures were found.
