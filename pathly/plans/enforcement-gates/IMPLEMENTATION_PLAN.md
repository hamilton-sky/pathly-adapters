# Enforcement Gates — Implementation Plan

## Overview

Adds a `run_gates()` function to `fsm.py` and wires it into `complete_stage` in `fsm_ops.py`
between transition evaluation (step 4) and transition actions (step 5). Gates are declared in
the flow YAML under a `gates:` key and run identically whether Claude Code or Codex is driving.
A failing gate writes an `on_fail` feedback file, appends a `GATE_FAILED` event, and returns a
blocked response — reusing the existing feedback routing machinery with zero new routing code.

## Layer Architecture

```
team.flow.yaml  (gate declarations)
       │  gates: { BUILDING->REVIEWING: [...] }
       ▼
fsm.py: run_gates()          ← NEW: pure Python, zero LLM imports
       │  primitives: require_artifact | verify_gate | scope_gate
       ▼
fsm_ops.py: complete_stage() ← MODIFIED: call run_gates() between steps 4 and 5
       │  on failure → write feedback file + GATE_FAILED event → _blocked_response()
       ▼
feedback_routing machinery   ← UNCHANGED: routes on_fail file to correct agent
```

## Pre-flight

Before starting Conversation 1, run `pytest` and record any pre-existing failures as a known
baseline. Do not attribute baseline failures to this feature.

---

## Phases

### Phase 1: `run_gates()` skeleton + `require_artifact` + `verify_gate`   ← Conversation: 1

**File:** `src/pathly_orchestrator/fsm.py` — MODIFY: add `run_gates()` and helper functions

**Done when:** `run_gates()` exists in `fsm.py`, handles `require_artifact` and `verify_gate`
types, raises `RuntimeError` for unknown types, returns `None` on all-pass and a dict on first
failure, and writes the `on_fail` file + appends `GATE_FAILED` event on failure.

**Delivers stories:** S1 (verify_gate), S2 (require_artifact), S4, S5

**Depends on:** nothing — `fsm.py` already has `append_event`; no new imports needed beyond stdlib/pathlib

**Enables:** Phase 2 (wiring), Phase 3 (YAML + tests)

**Details:**
- Add near the bottom of `fsm.py`, after `run_transition_actions`.
- Function signature: `def run_gates(flow: dict, prev_state: str, next_state: str, storage_path: Path, topic: str, conv: int) -> dict | None:`
- Gate lookup: `gates.get(f"{prev_state}->{next_state}", []) + gates.get(f"->{next_state}", [])`
- `require_artifact`: `(storage_path / gate["artifact"]).exists()`
- `verify_gate`: call `_verify_passed(storage_path / gate["artifact"], gate["pass_marker"])` — read the file, check that its first non-blank line is exactly equal to `pass_marker` (not substring). If file absent or empty: fail.
- On failure: `_write_gate_feedback(storage_path, gate["on_fail"], reason_str)` writes to `storage_path/feedback/<on_fail>`; `append_event(storage_path, {"type": "GATE_FAILED", "gate": gtype, "transition": f"{prev_state}->{next_state}"})`. Return `{"gate_failed": gtype, "feedback_file": gate["on_fail"]}`.
- Private helpers: `_verify_passed(path, marker) -> bool`, `_write_gate_feedback(storage_path, filename, reason)`.

**Verify:** `pytest tests/test_fsm.py tests/test_gates.py -x`

---

### Phase 2: Wire `run_gates()` into `complete_stage`   ← Conversation: 1

**File:** `src/pathly_orchestrator/fsm_ops.py` — MODIFY: call `run_gates()` between steps 4 and 5

**Done when:** `complete_stage` calls `run_gates()` after `next_state` is computed and before
`run_transition_actions()`. On gate failure, it returns a blocked response using the existing
`_blocked_response()` helper without advancing state.

**Delivers stories:** S1, S2, S4

**Depends on:** Phase 1 (`run_gates()` must exist in `fsm.py`)

**Enables:** end-to-end gate enforcement

**Details:**
- Import `run_gates` from `fsm.py` at the top of `fsm_ops.py` (check existing imports first).
- Insert after `next_state = eval_result` (or after the `decide` branch resolves `next_state`) and before `run_transition_actions(...)`:
  ```python
  gate_failure = run_gates(
      flow_config, state_info["current_state"], next_state,
      storage_path, topic, state_info["conv"]
  )
  if gate_failure is not None:
      feedback = route_feedback(flow_config, storage_path)
      return _blocked_response(feedback, state_info)
  ```
- Gates must run **before** the `commit` transition action so a failing build is never committed.
- Do not modify `_blocked_response()` — reuse it as-is.

**Verify:** `pytest tests/test_fsm_ops.py tests/test_gates.py -x`

---

### Phase 3: Add `gates:` to `team.flow.yaml` + write `tests/test_gates.py`   ← Conversation: 1

**Files:**
- `src/pathly_data/core/flows/team.flow.yaml` — MODIFY: add `gates:` section
- `tests/test_gates.py` — CREATE: pure unit tests

**Done when:** `team.flow.yaml` has a `gates:` section with `verify_gate` on `BUILDING->REVIEWING`
and `require_artifact` on `REVIEWING->TESTING`. `tests/test_gates.py` exists and all tests pass.

**Delivers stories:** S2, S5

**Depends on:** Phases 1–2

**Enables:** Conversation 2 (scope_gate extends the same YAML section)

**Details — YAML addition:**
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
Add this block after `transition_actions:` in `team.flow.yaml`.

**Details — tests (apply CANDIDATE-004: baseline test run first):**
- `test_require_artifact_pass`: artifact present → `run_gates()` returns `None`.
- `test_require_artifact_fail`: artifact absent → returns dict with `gate_failed`, writes `on_fail` file, appends `GATE_FAILED` event, `STATE.json` not created/changed.
- `test_verify_gate_pass`: file present, first non-blank line is exactly `RESULT: PASS` → pass.
- `test_verify_gate_fail_absent`: file absent → fail.
- `test_verify_gate_fail_wrong_marker`: file present, marker in body but not line 1 → fail.
- `test_verify_gate_fail_empty`: file present but empty → fail.
- `test_unknown_gate_type_raises`: `run_gates()` with `type: "bogus"` → `RuntimeError`.
- `test_complete_stage_gate_blocks`: end-to-end — `complete_stage` with gate condition unmet returns blocked, state does not advance.
- `test_complete_stage_gate_then_advance`: after resolving feedback, second `complete_stage` call advances normally.

**Verify:** `pytest tests/test_gates.py -v`

---

### Phase 4: Add `scope_gate` primitive + `GATE_SKIPPED` event   ← Conversation: 2

**File:** `src/pathly_orchestrator/fsm.py` — MODIFY: add `scope_gate` branch in `run_gates()`

**Done when:** `run_gates()` handles `scope_gate` type: reads declared files from
`CONVERSATION_PROMPTS.md`, runs `git diff --name-only <baseline_sha>` (pinned to conv-start SHA),
fails if any diff path is outside the declared set, emits `GATE_SKIPPED` (not silent pass) when
no file list is declared or when baseline SHA is unavailable.

**Delivers stories:** S3, S4 (scope path)

**Depends on:** Phase 1 (`run_gates()` skeleton), Phase 2 (wiring)

**Enables:** Phase 5 (YAML update), Phase 6 (scope_gate tests)

**Details:**
- Add `elif gtype == "scope_gate":` branch calling `_scope_clean(storage_path, gate["scope_file"], conv_start_sha)`.
- `_scope_clean(storage_path, scope_file, baseline_sha) -> bool | str`:
  - Read `storage_path / scope_file`; parse declared file paths (lines starting with `-` or `` ` ``).
  - If no declared paths found: `append_event(storage_path, {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "no_declared_scope"})` → return `True` (pass).
  - Run `subprocess.run(["git", "diff", "--name-only", baseline_sha], ...)` from project root (3 levels up from storage_path, matching `run_transition_actions` logic).
  - If baseline_sha is None or git fails: emit `GATE_SKIPPED` with `reason: "no_baseline_sha"` → return `True`.
  - Any diff path not in declared set → return `False`.
- Baseline SHA: read from `STATE.json["conv_start_sha"]` if present (written by the orchestrator at conversation start — check if this key exists first; if not, treat as unavailable).
- Project root depth: reuse the `storage_template` depth logic already in `run_transition_actions`.

**Verify:** `pytest tests/test_gates.py -x`

---

### Phase 5: Add `scope_gate` to `team.flow.yaml` + harden `verify_gate`   ← Conversation: 2

**Files:**
- `src/pathly_data/core/flows/team.flow.yaml` — MODIFY: add scope_gate to `BUILDING->REVIEWING`
- `src/pathly_orchestrator/fsm.py` — already modified in Phase 4; verify `_verify_passed` uses exact line-1 match (should be done in Phase 1 — confirm, do not re-implement)

**Done when:** `BUILDING->REVIEWING` in the YAML has both `verify_gate` and `scope_gate` entries.
`_verify_passed` correctly rejects a file where `RESULT: PASS` appears only in the body.

**Delivers stories:** S3, S5

**Depends on:** Phase 4

**Details — YAML update:**
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
Add `SCOPE_VIOLATION` to `feedback_routing` in `team.flow.yaml` → routes to `builder`.

**Verify:** `pytest tests/test_gates.py -v`

---

### Phase 6: Extend `tests/test_gates.py` with scope_gate tests   ← Conversation: 2

**File:** `tests/test_gates.py` — MODIFY: add scope_gate test cases

**Done when:** All scope_gate tests pass. Full gate suite green.

**Delivers stories:** S3, S4

**Depends on:** Phases 4–5

**Details:**
- `test_scope_gate_pass`: diff contains only declared files → pass.
- `test_scope_gate_fail_undeclared_path`: diff has an undeclared path → fail, writes `SCOPE_VIOLATION.md`.
- `test_scope_gate_no_declared_scope`: no file list in scope_file → `GATE_SKIPPED` event emitted, gate passes.
- `test_scope_gate_no_baseline_sha`: no SHA in STATE.json → `GATE_SKIPPED` emitted, gate passes.
- `test_verify_gate_pass_marker_in_body_not_line1`: confirm `RESULT: PASS` in body only → fail.
- `test_full_suite_green`: `pytest tests/test_gates.py tests/test_fsm.py tests/test_fsm_ops.py` all pass.

**Verify:** `pytest tests/test_gates.py tests/test_fsm.py tests/test_fsm_ops.py -v`

---

## Prerequisites

- Python + pytest available (`pytest` or `python -m pytest`).
- `src/pathly_orchestrator/fsm.py` and `fsm_ops.py` confirmed present (glob before editing).
- `src/pathly_data/core/flows/team.flow.yaml` confirmed present.
- Pre-flight: run `pytest` and record baseline failures before starting Conv 1.

## Key Decisions

- **Gates run in `fsm.py`, not `fsm_ops.py`** — keeps the engine zero-import like all other FSM functions; `fsm_ops.py` only calls and wires.
- **Fail-fast gate ordering** — first failure stops evaluation and routes. Collecting all failures would require a new multi-failure feedback format; single-failure is consistent with existing `route_feedback` contract. Document this explicitly in a comment near `run_gates()`.
- **verify_gate uses line-1 exact match, not substring** — prevents `RESULT: PASS` embedded in a failure explanation from satisfying the gate.
- **scope_gate silently skips → `GATE_SKIPPED` event** — operators need visibility that enforcement is absent; a silent pass is not acceptable.
- **Commit action ordering** — `run_gates()` is called before `run_transition_actions()`, so a failing `BUILDING->REVIEWING` transition never triggers the commit action.
