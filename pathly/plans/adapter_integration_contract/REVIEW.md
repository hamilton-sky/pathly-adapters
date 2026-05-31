# REVIEW — adapter_integration_contract Conv 1

Date: 2026-06-01
Reviewer: reviewer agent
Files reviewed: `src/pathly_orchestrator/fsm_ops.py`, `tests/test_fsm_ops.py`
Stories in scope: S1.1, S1.2

## Outcome: FAIL (1 violation)

One acceptance criterion is not fully satisfied. See `feedback/REVIEW_FAILURES.md`.

## Summary

| Criterion | Result |
|---|---|
| S1.1 — `current_state` key on both endpoints | PASS |
| S1.1 — `agent_hint` neutral keys only | PASS |
| S1.1 — `codex_subagent` retains legacy keys | PASS |
| S1.1 — blocked/escalated shape includes `agent_hint`, `storage_path`, `stage_brief` | FAIL — corrupt-state path omits `storage_path` |
| S1.2 — agent-target feedback → `decision = "block"` | PASS |
| S1.2 — human-target feedback → `decision = "escalate"` | PASS |
| S1.2 — corrupt state → `decision = "escalate"` | PASS (value correct; shape incomplete) |
| S1.2 — gate failure + no routable feedback → `decision = "escalate"` | PASS |
| S1.2 — `recover_state` wrapped in try/except | PASS |

## Violation detail

`fsm_ops.py` lines 322–336 (`next_action`) and lines 415–429 (`complete_stage`) return inline
dicts for the corrupt-state escalate path. Both dicts include `agent_hint` and `stage_brief`
but omit `storage_path`. Every other blocked/escalated code path (via `_blocked_response`)
correctly includes `storage_path`.

Fix: add `"storage_path": str(storage_path)` to both inline escalate dicts.

## Test coverage note

No test exercises the `recover_state` exception branch. Adding a test that patches
`recover_state` to raise would catch the shape violation and prevent regression.
