# Enforcement Gates — Progress

## Status: COMPLETE

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1 | verify_gate on BUILDING→REVIEWING | Conv 1 | TODO |
| S2 | require_artifact on REVIEWING→TESTING | Conv 1 | TODO |
| S3 | scope_gate on BUILDING→REVIEWING | Conv 2 | TODO |
| S4 | Gate failures use existing feedback routing | Conv 1 + Conv 2 | TODO |
| S5 | Gates declared in flow YAML | Conv 1 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1–3 | S1, S2, S4, S5 | DONE | `pytest tests/test_gates.py tests/test_fsm_ops.py -v` |
| 2 | 4–6 | S3, S4 (scope) | DONE | `pytest tests/test_gates.py tests/test_fsm.py tests/test_fsm_ops.py -v` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 1 | `src/pathly_orchestrator/fsm.py` | Add `run_gates()` + `require_artifact` + `verify_gate` | `run_gates()` exists, handles 2 types, raises on unknown | DONE |
| 1 | 2 | `src/pathly_orchestrator/fsm_ops.py` | Wire `run_gates()` into `complete_stage` | Gate check runs before commit action | DONE |
| 1 | 3 | `src/pathly_data/core/flows/team.flow.yaml` + `tests/test_gates.py` | Add `gates:` YAML section + Conv 1 tests | All Conv 1 tests pass | DONE |
| 2 | 4 | `src/pathly_orchestrator/fsm.py` | Add `scope_gate` + `GATE_SKIPPED` event | scope_gate branch exists with baseline pinning | DONE |
| 2 | 5 | `src/pathly_data/core/flows/team.flow.yaml` | Add scope_gate entry + SCOPE_VIOLATION routing | YAML has both gates on BUILDING->REVIEWING | DONE |
| 2 | 6 | `tests/test_gates.py` | scope_gate tests + full suite | All tests green | DONE |

## Prerequisites

- `pytest` available
- Pre-flight baseline: run `pytest` before Conv 1 and record failures

## Blocked By

- Nothing
