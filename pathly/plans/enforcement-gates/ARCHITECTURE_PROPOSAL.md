# Enforcement Gates — Architecture Proposal

## Problem Statement

Pathly's hook-based enforcement only fires under Claude Code. Codex (and future CLI hosts)
call the FSM server directly via `POST /complete_stage` but never run local hooks, so any
rule enforced in a hook is invisible to them. The gap means the same pipeline has different
enforcement depending on which tool is driving — undermining the cross-tool portability promise.

## Proposed Solution

Add a `run_gates()` function to `fsm.py` — the pure-Python, zero-LLM engine that both Claude
Code and Codex already call. Gates run inside `complete_stage` between transition evaluation
and transition actions. Rules are declared in the flow YAML under a `gates:` key. A failing
gate writes a feedback file and returns a blocked response using the existing feedback routing
machinery; no new routing code is needed.

## Layer Breakdown

```
team.flow.yaml               (gate declarations — operator-facing config)
     │  gates: { BUILDING->REVIEWING: [...] }
     ▼
fsm.py: run_gates()          (NEW — pure Python, zero LLM imports)
     │  lookup: prev->next + wildcard ->next
     │  primitives: require_artifact | verify_gate | scope_gate
     │  on fail: write feedback file + append GATE_FAILED event
     ▼
fsm_ops.py: complete_stage() (MODIFIED — call run_gates() between steps 4 and 5)
     │  step 4: evaluate_transition_rules → next_state
     │  step 4.5: run_gates() ← NEW insertion point
     │  step 5: run_transition_actions (commit, etc.)
     ▼
feedback_routing machinery   (UNCHANGED — routes on_fail file to correct agent)
```

## Key Design Decisions

### Decision 1: Gates live in `fsm.py`, not `fsm_ops.py`

- **Options considered**: (A) `fsm.py` alongside other engine functions, (B) `fsm_ops.py` alongside the caller, (C) new module `gates.py`
- **Chosen**: A — `fsm.py`
- **Rationale**: `fsm.py` is already the zero-import engine. All FSM primitives (`recover_state`, `evaluate_transition_rules`, `route_feedback`, `run_transition_actions`) live here. Gates are a peer primitive. A new module adds indirection without benefit.

### Decision 2: Fail-fast gate ordering

- **Options considered**: (A) fail on first gate failure, (B) collect all failures and surface them together
- **Chosen**: A — fail-fast
- **Rationale**: The existing `route_feedback` contract handles exactly one feedback file at a time. Multi-failure would require a new feedback format and new routing logic. Fail-fast is consistent with the rest of the engine and keeps the feedback loop tight.

### Decision 3: `verify_gate` sentinel is first-non-blank-line exact match

- **Options considered**: (A) substring match anywhere in file, (B) exact first-non-blank-line match, (C) structured JSON sentinel
- **Chosen**: B
- **Rationale**: Substring match is gameable (a model writes `RESULT: PASS` inside a failure block). JSON sentinel is overkill and breaks human readability. First-non-blank-line exact match is simple, unambiguous, and easy to write correctly.

### Decision 4: scope_gate skips (with event) rather than fails when scope is undeclared

- **Options considered**: (A) hard fail if no declared scope, (B) silent pass, (C) GATE_SKIPPED event + pass
- **Chosen**: C
- **Rationale**: Hard fail would break all existing plans that lack explicit file declarations. Silent pass hides missing enforcement from operators. GATE_SKIPPED surfaces the absence without breaking the pipeline.

## Key Components

| Component | Location | Description |
|---|---|---|
| `run_gates()` | `fsm.py` | Main gate runner — looks up YAML gates, runs them in order, returns None or failure dict |
| `_verify_passed()` | `fsm.py` | Private helper — reads artifact, checks first non-blank line |
| `_scope_clean()` | `fsm.py` | Private helper — parses declared files, runs git diff, compares |
| `_write_gate_feedback()` | `fsm.py` | Private helper — writes on_fail file to feedback/ dir |
| `gates:` section | `team.flow.yaml` | YAML config — gate declarations keyed by transition |

## Interface Design

```python
def run_gates(
    flow: dict,
    prev_state: str,
    next_state: str,
    storage_path: Path,
    topic: str,
    conv: int,
) -> dict | None:
    """None = all gates passed. dict = first gate failure description."""
```

Callers: `complete_stage` in `fsm_ops.py` only.

## Risks

- **Baseline SHA absent**: scope_gate skips silently (mitigated by GATE_SKIPPED event).
- **Gate misconfiguration in YAML**: unknown `type` raises `RuntimeError` at runtime — caught by the server and returned as an error response; not a silent pass.
- **commit ordering**: if gates are accidentally placed after `run_transition_actions`, a failing build gets committed. Mitigated by explicit insertion-point specification in Phase 2 and a test (`test_complete_stage_gate_blocks`) that verifies state does not advance on failure.
