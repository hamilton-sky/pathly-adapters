# TEST FAILURES — adapter_integration_contract Conv 1

**Date:** 2026-06-01
**Test run:** `pytest -q tests/test_fsm_ops.py -v`
**Run result:** 18 passed, 0 failed — no execution failures.

The items below are coverage gaps (NOT COVERED), not test failures. All 18 tests passed.

---

## NOT COVERED: S1.2 — Gate failure with no routable feedback -> escalate

**Criterion (from USER_STORIES.md):**
> Gate failure with no routable feedback -> `decision = "escalate"`

**What is missing:**
No test in `tests/test_fsm_ops.py` exercises the path where `complete_stage` encounters a gate condition but finds no feedback file in the `feedback/` directory (or no recognized feedback routing entry). The correct behavior is that the FSM should return `decision = "escalate"`, but this is unverified.

**Expected:** A call to `complete_stage` (or `next_action`) with an empty or unrecognized `feedback/` directory should return `result["decision"] == "escalate"`.

**Actual:** Not tested. Implementation behavior for this path is unknown from tests alone.

**Suggested test name:** `test_escalate_when_no_routable_feedback`

---

## NOT COVERED: S1.2 — Adapter contract safeguard: escalate must be surfaced to user

**Criterion (from USER_STORIES.md):**
> The adapter can safely automate `continue` and `block`, but must surface `escalate` to the user.

**What is missing:**
No test verifies that escalate responses carry a shape that structurally prevents silent automation (e.g., absence of an auto-retry signal, or presence of a human-required marker). This is a contract-level assertion, not a unit behavior, but it is explicitly called out as an acceptance criterion.

**Expected:** An escalate response is distinguishable from continue/block in a way that is verifiable in the response payload (e.g., `decision == "escalate"` is insufficient alone if the adapter could treat it as continue — the test should confirm nothing in the escalate payload implies it is safe to auto-continue).

**Actual:** Not tested. The decision enum is correct but no test guards against adapter misuse of escalate.

**Suggested test name:** `test_escalate_response_not_continuable`

---

## Action required

Add two tests to `tests/test_fsm_ops.py` covering the above gaps.
No existing tests need to be fixed — all 18 pass.
