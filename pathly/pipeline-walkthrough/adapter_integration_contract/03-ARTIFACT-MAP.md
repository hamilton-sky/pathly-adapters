# Artifact Map — adapter_integration_contract

**Date:** 2026-06-01

## Feedback Files

| File                               | Written by       | Resolved by  |
|------------------------------------|------------------|--------------|
| TEST_FAILURES_conv1_attempt1.md    | team/test conv 1 | team/build   |

## Source Files Changed

| Path                                                    | Story      | What changed                                                                 |
|---------------------------------------------------------|------------|------------------------------------------------------------------------------|
| src/pathly_orchestrator/fsm_ops.py                      | S1.1, S1.2 | New `_agent_hint` with neutral keys; `_blocked_response` with escalate/block decision; `current_state` on both endpoints; storage_path in inline escalate dicts |
| tests/test_fsm_ops.py                                   | S1.1, S1.2 | 3 new tests: agent_hint neutral keys, codex_subagent legacy keys, escalate/block decision, blocked response shape, corrupt-state storage_path, escalate-when-no-feedback, escalate-not-continuable |
| src/pathly_data/adapters/codex/SKILL_EXECUTION.md       | S2.1, S2.2 | Added `## Decisions` block documenting continue/block/escalate semantics    |
| tests/test_setup.py                                     | S2.1, S2.2 | 3 new assertions: decision values present, agent_hint present, codex_subagent absent as primary dispatch |
| pyproject.toml                                          | —          | Removed UTF-8 BOM that was blocking pytest discovery                         |
