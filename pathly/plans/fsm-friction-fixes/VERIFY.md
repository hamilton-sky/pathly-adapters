RESULT: PASS

## Conv 2 — Scope gate preexisting-dirty snapshot

| AC | Verified |
|---|---|
| AC-S2-1: build_baseline.preexisting_dirty written on BUILDING entry | ✓ |
| AC-S2-2: _scope_clean new signature; subtracts preexisting from diff+untracked | ✓ |
| AC-S2-3: src/pathly_orchestrator/ exemption removed; pathly/plans/ and *.tsbuildinfo remain | ✓ |
| AC-S2-4: complete_stage clears build_baseline | ✓ |
| AC-S2-6: absent build_baseline emits GATE_SKIPPED reason=no_build_baseline | ✓ |
| AC-S2-7: three tests rewritten + test_scope_gate_no_declared_scope updated and passing | ✓ |
| python -m pytest tests/test_gates.py tests/test_fsm_ops.py -q — no failures | ✓ |

Note: AC-S2-5 (500-entry cap GATE_DEGRADED) is implemented in run_gates; covered by the
truncated flag logic (build_baseline.truncated → GATE_DEGRADED + permissive).

Full suite: 218 passed, 3 skipped.
