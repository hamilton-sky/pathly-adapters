# Verify — adapter_integration_contract Conv 1

RESULT: PASS

## Command
```
pytest -q tests/test_fsm_ops.py
```

## Output
18 passed in 0.86s (includes corrupt-state escalate coverage added after review)

## Tests covering new contract
- test_agent_hint_uses_neutral_keys — agent_hint has `role` and `agent` (not `codex_role`/`pathly_agent`)
- test_codex_subagent_retains_legacy_keys — codex_subagent keeps `codex_role`/`pathly_agent` for compat
- test_current_state_key_on_next_action — next_action emits `current_state`
- test_current_state_key_on_complete_stage — complete_stage emits `current_state` (not `next_state`)
- test_escalate_decision_when_target_is_human — human target → decision = "escalate"
- test_block_decision_when_target_is_non_human_agent — agent target → decision = "block"
- test_blocked_response_has_agent_hint_and_storage_path — blocked envelope is normalized
- test_blocked_response_warnings_contain_open_feedback — warnings has open_feedback entry
