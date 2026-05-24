# Plan — Cross-Tool Enforcement Gates (Part B)

> Never ask the model to follow a rule you can check in code. The **only** enforcement layer shared by all hosts is the FSM (pure Python, hit over HTTP). So portable rules live there, expressed as **gates** the FSM runs before it accepts a state transition.

Host hooks (`pathly_hooks/*.py`) fire **only under Claude Code** (the README "hook parity gap"). Gates run inside the FSM server, which **both Claude and Codex already call** via `POST /complete_stage`. So a gate enforces a rule identically no matter which CLI is driving.

**Tradeoff (accept it):** gates are **checkpoint** enforcement — caught at the handoff between stages, not mid-keystroke. They cannot *prevent* a bad edit; they *catch it at the gate*, refuse to advance, and route back. For almost every Pathly rule that is exactly right: you don't need to block the keystroke, you need to refuse to call the work "done."

---

## Status

| Thing | Status |
|---|---|
| Server-side enforcement gates | ❌ not built — this plan |

---

## Where it plugs in

`fsm_ops.complete_stage()` (`src/pathly_orchestrator/fsm_ops.py:130`) already does, in order:

1. delete resolved feedback files
2. `recover_state`
3. `route_feedback` → if blocked, return (no advance)
4. `evaluate_transition_rules` → compute `next_state`
5. `run_transition_actions`
6. `write_state` + append `STATE_TRANSITION`

**Insert gates between step 4 and step 5.** If a gate fails: write a feedback file, append a `GATE_FAILED` event, and **return a blocked response without advancing**. The next `next_action` call then routes that feedback file to the owning agent through the *existing* `feedback_routing` machinery — zero new routing code.

---

## New surface

### 1. `gates:` section in the flow YAML

Keyed by transition (`FROM->TO`) or by wildcard (`->TO`), mirroring `transition_actions`:

```yaml
# team.flow.yaml (addition)
gates:
  BUILDING->REVIEWING:
    - type: verify_gate          # a verify result must exist and say PASS
      artifact: VERIFY.md
      pass_marker: "RESULT: PASS"
      on_fail: REVIEW_FAILURES.md # feedback file to write → routes to builder
    - type: scope_gate            # working-tree diff must stay within declared files
      scope_file: CONVERSATION_PROMPTS.md
      on_fail: SCOPE_VIOLATION.md
  REVIEWING->TESTING:
    - type: require_artifact
      artifact: REVIEW.md
      on_fail: HUMAN_QUESTIONS.md
```

### 2. `run_gates()` in `fsm.py`

```python
def run_gates(flow, prev_state, next_state, storage_path, topic, conv) -> dict | None:
    """Return None if all gates pass; else a dict describing the failure.
    On failure, write the on_fail feedback file (dual-write to artifacts too)
    and append a GATE_FAILED event. Never advances state."""
    gates = (flow.get("gates") or {})
    to_run = gates.get(f"{prev_state}->{next_state}", []) + gates.get(f"->{next_state}", [])
    for gate in to_run:
        gtype = gate["type"]
        if gtype == "require_artifact":
            ok = (storage_path / gate["artifact"]).exists()
        elif gtype == "verify_gate":
            ok = _verify_passed(storage_path / gate["artifact"], gate["pass_marker"])
        elif gtype == "scope_gate":
            ok = _scope_clean(storage_path, gate["scope_file"])  # git diff vs declared files
        else:
            raise RuntimeError(f"Unknown gate type: {gtype!r}")
        if not ok:
            _write_feedback(storage_path, gate["on_fail"], _gate_reason(gate))
            append_event(storage_path, {"type": "GATE_FAILED",
                                        "gate": gtype, "transition": f"{prev_state}->{next_state}"})
            return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
    return None
```

Gate primitives:
- **`require_artifact`** — file must exist.
- **`verify_gate`** — read the artifact, require a pass marker. Stops "claimed success without running verify."
- **`scope_gate`** — `git diff --name-only` (working tree) vs the file list declared in the conv's `CONVERSATION_PROMPTS.md`; any path outside the declared set fails.

### 3. Wire into `complete_stage`

```python
# after next_state is computed, before run_transition_actions(...)
gate_failure = run_gates(flow_config, state_info["current_state"], next_state,
                         storage_path, topic, state_info["conv"])
if gate_failure is not None:
    feedback = route_feedback(flow_config, storage_path)
    return _blocked_response(feedback, state_info)  # reuses existing machinery
```

---

## Why this is the right shape

- **Cross-tool by construction** — lives in `fsm.py`/`fsm_ops.py`, zero LLM/host imports, runs for anyone hitting `/complete_stage`.
- **Reuses everything** — failures become feedback files; `feedback_routing` + `route_feedback` already send them to the right agent and block the pipeline. The Monitor already shows `FILE_CREATED`; add `GATE_FAILED` to the event color map.
- **Declarative** — rules live in the flow YAML next to the transitions they guard, not buried in prose.

---

## Tests (pure, fast)

- `run_gates` returns `None` when artifact present / verify passes / diff in-scope.
- `require_artifact` missing → writes `on_fail` file + `GATE_FAILED` event, no `STATE.json` change.
- `verify_gate` artifact present but marker absent → fail.
- `scope_gate` with a diff touching an undeclared path → fail; in-scope diff → pass.
- `complete_stage` end-to-end: gate failure returns a blocked response and state does **not** advance; second call after the agent resolves the feedback file advances normally.

---

## Open issues

- **`scope_gate` diff baseline** — `git diff --name-only` defaults to HEAD, but HEAD at `complete_stage` time may include prior-conv commits. Must pin baseline to the commit at conversation start, not HEAD. Otherwise a gate on conv 3 may see conv 2 files and pass incorrectly.

- **`verify_gate` pass_marker is a substring match** — a model could write "RESULT: PASS" inside a failure explanation. A structured sentinel at line 1 of the artifact (exact, not substring) would be more robust.

- **`scope_gate` no-ops silently when no file list is declared** — "skip + a one-line note" is not enough. Must emit a visible `GATE_SKIPPED` event the Monitor surfaces, so operators know enforcement is absent.

- **Gate ordering within a transition** — the first failure stops evaluation (fail-fast). Whether to collect all failures and show them together is an open design choice; document the decision explicitly.

- **Don't double-commit** — `BUILDING->REVIEWING` already runs a `commit` action; gates must run **before** that action so a failing build is never committed. Verify this ordering is enforced in `complete_stage`.

---

## Recommended start

Begin with `verify_gate` on `BUILDING->REVIEWING`. It is the highest-value rule (stops "claimed success without verify") and has no baseline ambiguity — it just checks file content.
