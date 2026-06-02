# Review Failures — Conv 2

Two IMPL violations found and fixed inline before PASS:

1. **[IMPL] fsm_ops.py:115** — `import logging` was nested inside `except` block. Fixed: moved to module top-level imports (line 7).

2. **[IMPL] state.py:184** — `resolve_block(block_name, {})` passed empty dict where `set[str] | None` is expected. Fixed: changed to `resolve_block(block_name, None)`.

One [ARCH] violation waived:

3. **[ARCH] state.py:172 — WAIVED** — Reviewer claimed `state.py → compose.py` dependency violates a `compose → state → fsm` layering diagram. Premise is incorrect: `compose.py` has zero internal project imports (no import from `state.py` or `fsm_ops.py`), so no cycle exists. The dependency is a clean DAG. Architecture proposal mandates block-name validation in the flow validator; `resolve_block` from `compose.py` is the correct API to call.

All tests pass after fixes: 395 passed, 3 skipped.
