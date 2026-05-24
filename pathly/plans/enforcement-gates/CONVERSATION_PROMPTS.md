# Enforcement Gates — Conversation Guide

Split into 2 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Core gate engine (Phases 1–3)

**Stories delivered:** S1, S2, S4, S5

**Prompt to paste:**
```
Read plans/enforcement-gates/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Enforcement Gates Conversation 1 (Phases 1–3) from plans/enforcement-gates/IMPLEMENTATION_PLAN.md.

**Pre-flight:** Run `pytest` and record any pre-existing failures as baseline before editing anything.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/fsm.py` — add `run_gates()` with `require_artifact` and `verify_gate` primitives
- `src/pathly_orchestrator/fsm_ops.py` — wire `run_gates()` into `complete_stage` between steps 4 and 5
- `src/pathly_data/core/flows/team.flow.yaml` — add `gates:` section
- `tests/test_gates.py` — CREATE: unit tests for Conv 1

Scope:

Phase 1 — `run_gates()` in `fsm.py`:
- Add `run_gates(flow, prev_state, next_state, storage_path, topic, conv) -> dict | None` near the bottom of `fsm.py` after `run_transition_actions`.
- Gate lookup: `gates.get(f"{prev_state}->{next_state}", []) + gates.get(f"->{next_state}", [])`.
- `require_artifact`: check `(storage_path / gate["artifact"]).exists()`.
- `verify_gate`: add `_verify_passed(path, marker) -> bool` — read the file, find the first non-blank line, check it is exactly equal to `marker` (not substring). File absent or empty: return False.
- On any failure: call `_write_gate_feedback(storage_path, gate["on_fail"], reason)` which writes to `storage_path/feedback/<on_fail>` (create feedback/ dir if absent); append `{"type": "GATE_FAILED", "gate": gtype, "transition": f"{prev_state}->{next_state}"}` event via `append_event`. Return `{"gate_failed": gtype, "feedback_file": gate["on_fail"]}`.
- Unknown gate type: raise `RuntimeError(f"Unknown gate type: {gtype!r}")`.
- Add a one-line comment above the loop documenting the fail-fast ordering decision: gates stop at the first failure.

Phase 2 — Wire into `complete_stage` in `fsm_ops.py`:
- Import `run_gates` from the fsm module (check existing imports).
- After `next_state` is resolved (after the decide-branch or `next_state = eval_result`) and BEFORE `run_transition_actions(...)`:
  ```python
  gate_failure = run_gates(
      flow_config, state_info["current_state"], next_state,
      storage_path, topic, state_info["conv"]
  )
  if gate_failure is not None:
      feedback = route_feedback(flow_config, storage_path)
      return _blocked_response(feedback, state_info)
  ```
- Do NOT modify `_blocked_response()`.

Phase 3 — YAML + tests:
- Add to `team.flow.yaml` after `transition_actions:`:
  ```yaml
  gates:
    BUILDING->REVIEWING:
      - type: verify_gate
        artifact: VERIFY.md
        pass_marker: "RESULT: PASS"
        on_fail: REVIEW_FAILURES.md
    REVIEWING->TESTING:
      - type: require_artifact
        artifact: REVIEW.md
        on_fail: HUMAN_QUESTIONS.md
  ```
- Create `tests/test_gates.py` with these tests (use tmp_path fixture, no mocks):
  - `test_require_artifact_pass`
  - `test_require_artifact_fail` (verifies on_fail written + GATE_FAILED event + no STATE.json change)
  - `test_verify_gate_pass`
  - `test_verify_gate_fail_absent`
  - `test_verify_gate_fail_wrong_marker` (RESULT: PASS in body but not line 1 → fail)
  - `test_verify_gate_fail_empty`
  - `test_unknown_gate_type_raises`
  - `test_complete_stage_gate_blocks` (end-to-end: state does not advance)
  - `test_complete_stage_gate_then_advance` (second call after feedback resolved: state advances)

Architectural rules:
- `run_gates()` must have zero LLM/host SDK imports — stdlib + pathlib only.
- Do NOT touch scope_gate yet (that is Conversation 2).
- Do NOT modify `evaluate_transition_rules`, `route_feedback`, or `recover_state`.

Do NOT touch `scope_gate`, Monitor event colors, or any flow file other than `team.flow.yaml`.

Verify: `pytest tests/test_gates.py tests/test_fsm_ops.py -v`
After done, update plans/enforcement-gates/PROGRESS.md phases 1–3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `run_gates()` live in `fsm.py`, wired in `fsm_ops.py`, `gates:` in `team.flow.yaml`, all Conv 1 tests green.
**Files touched:** `src/pathly_orchestrator/fsm.py`, `src/pathly_orchestrator/fsm_ops.py`, `src/pathly_data/core/flows/team.flow.yaml`, `tests/test_gates.py`

---

## Conversation 2: scope_gate + hardening (Phases 4–6)

**Stories delivered:** S3, S4 (scope path)

**Prompt to paste:**
```
Read plans/enforcement-gates/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Enforcement Gates Conversation 2 (Phases 4–6) from plans/enforcement-gates/IMPLEMENTATION_PLAN.md.

Conversation 1 is complete. `run_gates()` exists in `fsm.py` with `require_artifact` and `verify_gate`. `team.flow.yaml` has a `gates:` section. All Conv 1 tests pass.

**Pre-flight (do this before writing any code):** Grep the codebase for `conv_start_sha`. Confirm the orchestrator is writing this key to `STATE.json` at conversation start. If the key is absent, stop and report — scope_gate will silently skip on every call without it, making the gate non-enforcing. Do not proceed until this is confirmed or added as a prerequisite.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/fsm.py` — add `scope_gate` branch + `GATE_SKIPPED` event; confirm `_verify_passed` uses line-1 exact match
- `src/pathly_data/core/flows/team.flow.yaml` — add `scope_gate` to `BUILDING->REVIEWING` + `SCOPE_VIOLATION` routing
- `tests/test_gates.py` — extend with scope_gate tests

Scope:

Phase 4 — `scope_gate` in `fsm.py`:
- Add `elif gtype == "scope_gate":` in the `run_gates()` loop calling `_scope_clean(storage_path, gate["scope_file"], conv_start_sha)`.
- `conv_start_sha`: read from `STATE.json["conv_start_sha"]` if the key exists; else `None`.
- `_scope_clean(storage_path, scope_file, baseline_sha) -> bool`:
  - Read `storage_path / scope_file`. Parse declared file paths (lines starting with `-` or backtick).
  - If no declared paths: emit `GATE_SKIPPED` event with `reason: "no_declared_scope"` → return `True`.
  - If `baseline_sha` is None: emit `GATE_SKIPPED` event with `reason: "no_baseline_sha"` → return `True`.
  - Run `subprocess.run(["git", "diff", "--name-only", baseline_sha], cwd=project_root, ...)`.
  - If git fails: emit `GATE_SKIPPED` with `reason: "git_diff_failed"` → return `True`.
  - Any diff path not in declared set → return `False`.
  - Project root: use the same `storage_template` depth logic as `run_transition_actions` (3 levels up for `pathly/plans/{topic}/`).

Phase 5 — YAML update:
- Update `gates:` in `team.flow.yaml`:
  ```yaml
  gates:
    BUILDING->REVIEWING:
      - type: verify_gate
        artifact: VERIFY.md
        pass_marker: "RESULT: PASS"
        on_fail: REVIEW_FAILURES.md
      - type: scope_gate
        scope_file: CONVERSATION_PROMPTS.md
        on_fail: SCOPE_VIOLATION.md
    REVIEWING->TESTING:
      - type: require_artifact
        artifact: REVIEW.md
        on_fail: HUMAN_QUESTIONS.md
  ```
- Add `SCOPE_VIOLATION: builder` to `feedback_routing` in `team.flow.yaml`.
- Confirm `_verify_passed` (written in Conv 1) uses exact line-1 match, not substring. Do not rewrite it if already correct.

Phase 6 — Extend tests:
- Add to `tests/test_gates.py`:
  - `test_scope_gate_pass` (diff only declared files → pass)
  - `test_scope_gate_fail_undeclared_path` (undeclared path in diff → fail, SCOPE_VIOLATION.md written)
  - `test_scope_gate_no_declared_scope` (no file list in scope_file → GATE_SKIPPED emitted, pass)
  - `test_scope_gate_no_baseline_sha` (no SHA in STATE.json → GATE_SKIPPED emitted, pass)
  - `test_verify_gate_pass_marker_in_body_not_line1` (confirm line-1 sentinel correctness)
- Run the full suite to confirm no regressions.

Architectural rules:
- `_scope_clean` must use subprocess for git (already allowed by existing fsm.py imports — check `import subprocess` is present).
- GATE_SKIPPED is not a failure — it must NOT write an on_fail file or block the transition.
- Do NOT touch `evaluate_transition_rules`, `route_feedback`, or `recover_state`.

Do NOT touch any other flow YAML files (explore.flow.yaml, test.flow.yaml, debug.flow.yaml).

Verify: `pytest tests/test_gates.py tests/test_fsm.py tests/test_fsm_ops.py -v`
After done, update plans/enforcement-gates/PROGRESS.md phases 4–6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** All three gate types live and tested. Full test suite green. `team.flow.yaml` has both gates on `BUILDING->REVIEWING`.
**Files touched:** `src/pathly_orchestrator/fsm.py`, `src/pathly_data/core/flows/team.flow.yaml`, `tests/test_gates.py`
