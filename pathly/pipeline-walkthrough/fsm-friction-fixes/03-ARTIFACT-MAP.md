# fsm-friction-fixes — Artifact Map

## Feedback Files

| File | Written by | Resolved by | Notes |
|------|------------|-------------|-------|
| REVIEW_FAILURES.md (Conv 1) | reviewer | builder | Missing GATE_DEGRADED test |
| REVIEW_FAILURES.md (Conv 3) | reviewer | builder | `_count_planned_convs` regex overcounting |
| HUMAN_QUESTIONS.md | FSM gate | resolved via `complete_stage resolved_files` | REVIEW.md artifact missing at first REVIEWING→TESTING attempt |

## Source Files Changed

| Path | Story | What changed |
|------|-------|--------------|
| `src/pathly_orchestrator/http_server.py` | S1 | Added auto-start logic: server spawns itself as background process on first CLI invocation if not already running |
| `src/pathly_data/core/skills/utilities/fsm-call.md` | S1 | Updated server-ensure block to use auto-start path instead of requiring manual terminal launch |
| `src/pathly_orchestrator/fsm_http_client.py` | S1 | Client-side auto-start: health-check → spawn → retry pattern |
| `src/pathly_orchestrator/fsm_ops.py` | S2, S3 | `build_baseline` snapshot at BUILDING entry; `_scope_clean` subtracts `preexisting_dirty`; `GATE_DEGRADED`/`GATE_SKIPPED` events; `_count_planned_convs` (unique set + anchored match); `convs_total`/`convs_done` stamping |
| `src/pathly_orchestrator/fsm.py` | S3 | `on_state_counter` rule level (Level 2.5) in `evaluate_transition_rules`; `convs_done` atomic increment in `update_progress` conv_done branch |
| `src/pathly_data/core/flows/team.flow.yaml` | S3 | REVIEWING block: added `on_state_counter` rule; `MORE_CONVS_NEEDED.md` retained as backwards-compat fallback |
| `src/pathly_data/core/skills/team/review.md` | S3 | Removed instruction to write/delete `MORE_CONVS_NEEDED.md` |
| `tests/test_gates.py` | S2 | Tests for `build_baseline` scope gate: preexisting-dirty exclusion, `GATE_DEGRADED` permissive mode, `GATE_SKIPPED` no-baseline |
| `tests/test_on_state_counter.py` | S3 | 4 tests: condition met → BUILDING, condition unmet → TESTING (default), missing field → fallthrough, malformed op → fallthrough |
| `tests/test_http_server.py` | S1 | Tests for server auto-start endpoint behaviour |
| `tests/test_fsm_http_client.py` | S1 | Tests for client-side auto-start + retry logic |
