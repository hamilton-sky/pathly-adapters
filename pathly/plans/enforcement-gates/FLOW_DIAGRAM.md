# Enforcement Gates — Flow Diagram

## Happy Path: BUILDING→REVIEWING with gates passing

```
POST /complete_stage  (builder calls after verify passes)
        │
        ▼
complete_stage()  [fsm_ops.py]
        │
        ├─ recover_state()         → current_state = BUILDING
        ├─ route_feedback()        → None (no open feedback)
        ├─ evaluate_transition_rules() → next_state = REVIEWING
        │
        ▼
run_gates(flow, BUILDING, REVIEWING, storage_path)   ← NEW
        │
        ├─ verify_gate: VERIFY.md exists?  ──► yes
        │       first non-blank line == "RESULT: PASS"? ──► yes ──► pass
        │
        ├─ scope_gate: declared files in CONVERSATION_PROMPTS.md?
        │       git diff --name-only <conv_start_sha>
        │       all paths in declared set? ──► yes ──► pass
        │
        └─ returns None (all gates passed)
        │
        ▼
run_transition_actions()   (commit action runs here)
        │
        ▼
write_state(REVIEWING) + STATE_TRANSITION event
        │
        ▼
Response: {next_state: REVIEWING, ...}
```

## Gate Failure Path: verify_gate fails

```
run_gates()
        │
        ├─ verify_gate: VERIFY.md exists?  ──► no (or wrong line 1)
        │
        ▼
_write_gate_feedback(storage_path, "REVIEW_FAILURES.md", reason)
        │
append_event(GATE_FAILED {gate: verify_gate, transition: BUILDING->REVIEWING})
        │
        └─ returns {"gate_failed": "verify_gate", "feedback_file": "REVIEW_FAILURES.md"}
        │
        ▼ (back in complete_stage)
route_feedback() → {file: REVIEW_FAILURES.md, target_agent: builder}
        │
_blocked_response(feedback, state_info)   ← UNCHANGED, reused as-is
        │
        ▼
Response: blocked (state NOT advanced, no commit)
        │
        ▼
Builder reads REVIEW_FAILURES.md, fixes verify, calls complete_stage again
        │
        ▼
run_gates() → None → advances to REVIEWING
```

## GATE_SKIPPED Path: scope_gate, no declared scope

```
run_gates() → scope_gate branch
        │
_scope_clean(): read CONVERSATION_PROMPTS.md
        │
        └─ no parseable file list found
        │
append_event(GATE_SKIPPED {gate: scope_gate, reason: "no_declared_scope"})
        │
        └─ return True (pass — no feedback file written)
        │
        ▼
Gate loop continues to next gate (or returns None if no more gates)
```

## Component Legend

| Symbol | Meaning |
|---|---|
| `complete_stage()` | Orchestration entry point in `fsm_ops.py` — calls all FSM steps |
| `run_gates()` | NEW gate runner in `fsm.py` — evaluates YAML-declared gates |
| `_verify_passed()` | Private helper — checks artifact sentinel |
| `_scope_clean()` | Private helper — checks git diff against declared scope |
| `_blocked_response()` | Existing helper in `fsm_ops.py` — reused without changes |
| `GATE_FAILED` | Event type written to `EVENTS.jsonl` on any gate failure |
| `GATE_SKIPPED` | Event type written to `EVENTS.jsonl` when a gate cannot evaluate |
