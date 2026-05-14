# TEST_FAILURES.md — fsm-transition-actions

Generated: 2026-05-14

## Test run summary

- pytest (excluding test_orchestrator.py): 85 passed
- pytest test_orchestrator.py: COLLECTION ERROR (import failure, unrelated to this feature)
- Validation commands: executed directly via Python

---

## Failures and gaps

### FAIL 1 — test_orchestrator.py cannot be collected (pre-existing import error)

**Story:** S2.1 (Orchestrator executes transition_actions generically)
**Criterion:** Not directly — this is test infrastructure breakage.

**What failed:** `tests/test_orchestrator.py` fails to import:
```
ImportError: cannot import name 'VALID_STATES' from 'pathly_orchestrator.state'
```
The test file imports `VALID_STATES`, `TRANSITIONS`, `STATES` from `pathly_orchestrator.state`, but `state.py` was generalized in the upstream `fsm-configurable` feature (Phase 5c) and no longer exports these module-level constants. The constants were replaced by flow-agnostic functions (`valid_states(flow)`, `flow_transitions(flow)`).

**Expected:** test_orchestrator.py imports successfully and all its tests run.
**Actual:** Collection error; 0 tests in that file run.

**Root cause:** test_orchestrator.py was written for the old state.py API (before fsm-configurable Phase 5c). It was not updated when state.py was generalized.

**Impact:** This is a pre-existing break introduced by the upstream feature, not by fsm-transition-actions itself. However it means no automated test coverage exists for any orchestrator-level behavior.

---

### NOT COVERED 1 — No automated tests for transition_actions at all

**Stories affected:** S1.1, S1.2, S2.1, S3.1

**Criterion gap:** Zero tests in the test suite cover `transition_actions` parsing, validation, or execution. The test context confirmed this pre-existing gap. Specifically missing:

- No test for `get_transition_actions()` returning correct dict from a flow YAML.
- No test for `validate_flow_cli()` with a valid flow containing transition_actions.
- No test for `validate_flow_cli()` warning when `transition_actions` is absent.
- No test for `validate_flow_cli()` erroring on unknown action type.
- No test for `validate_flow_cli()` erroring on FROM->TO key not in transitions.
- No test for orchestrator executor block no-op behavior when no transition_actions match.

**Recommendation:** Add a `tests/test_transition_actions.py` covering the above cases. The validator functions are pure Python and easy to unit-test.

---

## Full test plan

### Story S1.1 — Declarative transition_actions in flow YAML schema

```
Story S1.1: Declarative transition_actions in flow YAML schema
  Criterion: transition_actions present in team.flow.yaml with BUILDING->REVIEWING (git_commit) and RETRO->DONE (archive_artifacts)
  Test: Read team.flow.yaml lines 80-85; validate via validate_flow_cli
  Status: PASS
  Notes: Field present at lines 80-85. git_commit with message at BUILDING->REVIEWING, archive_artifacts at RETRO->DONE. Validation exits 0.

  Criterion: debug.flow.yaml contains a transition_actions key
  Test: Read debug.flow.yaml line 39; validate via validate_flow_cli
  Status: PASS
  Notes: transition_actions: {} present at line 39. Validation exits 0.

  Criterion: explore.flow.yaml contains a transition_actions key
  Test: Read explore.flow.yaml line 32; validate via validate_flow_cli
  Status: PASS
  Notes: transition_actions: {} present at line 32. Validation exits 0.

  Criterion: Every FROM->TO key references a transition pair that exists in that flow's transitions list
  Test: validate_flow_cli on all three flows; manual check
  Status: PASS
  Notes: team.flow.yaml BUILDING->REVIEWING and RETRO->DONE both exist in transitions. debug and explore have empty dicts. Validator confirms clean.

  Criterion: Action type values limited to git_commit, update_progress, archive_artifacts
  Test: Inject invalid action type into temp YAML; run validate_flow_cli
  Status: PASS
  Notes: Validator printed "Unknown action type 'invalid_action_type' in transition_actions[A->B]" and exited 1.

  Criterion: Flows without side effects may omit transition_actions entirely without breaking schema loading
  Test: Load flow YAML without transition_actions key; call get_transition_actions()
  Status: PASS
  Notes: get_transition_actions() returns {} when key absent. validate_flow_cli warns but exits 0.
```

### Story S1.2 — team.flow.yaml fully migrates all existing side effects

```
Story S1.2: team.flow.yaml fully migrates all existing side effects
  Criterion: BUILDING->REVIEWING declares git_commit with message "feat: complete building stage"
  Test: Read team.flow.yaml lines 81-83
  Status: PASS
  Notes: Exact message present at line 83.

  Criterion: RETRO->DONE declares archive_artifacts action
  Test: Read team.flow.yaml lines 84-85
  Status: PASS
  Notes: archive_artifacts action present at line 85.

  Criterion: Each action entry has exactly type (and message where required)
  Test: Read team.flow.yaml; inspect structure
  Status: PASS
  Notes: git_commit entry has type + message. archive_artifacts entry has type only (no message required). Both structurally correct.

  Criterion: grep "transition_actions" team.flow.yaml returns at least one match
  Test: grep on team.flow.yaml
  Status: PASS
  Notes: Key present at line 80.
```

### Story S2.1 — Orchestrator executes transition_actions generically

```
Story S2.1: Orchestrator executes transition_actions generically
  Criterion: All hardcoded git commit logic removed from orchestrator.md
  Test: grep -i "git commit" orchestrator.md; inspect all matches
  Status: PASS
  Notes: Only match is inside the generic executor block at line 103 describing the action handler. No flow-specific hardcoded commit.

  Criterion: All hardcoded artifact archiving logic removed from orchestrator.md
  Test: grep -i "artifact archiv" orchestrator.md; inspect all matches
  Status: PASS
  Notes: Only match is inside the generic executor block (archive_artifacts action description). No flow-specific hardcoded logic.

  Criterion: Orchestrator contains transition_actions executor block after EVENTS.jsonl append step
  Test: Read orchestrator.md lines 86-114
  Status: PASS
  Notes: "Execute transition_actions" section present at lines 86-114, immediately after the EVENTS.jsonl append step at line 84-85.

  Criterion: Executor looks up FROM->TO key and executes actions in YAML-declared order
  Test: Read orchestrator.md executor block
  Status: PASS
  Notes: Step 2 constructs "PREV_STATE->NEW_STATE" key; step 4 iterates in YAML list order (sequential).

  Criterion: Executor checks ->DONE wildcard when destination is DONE
  Test: Read orchestrator.md step 3 of executor block
  Status: PASS
  Notes: Step 3 explicitly says "Also check '->NEW_STATE' as a wildcard".

  Criterion: Transition with no matching transition_actions entry executes cleanly as no-op
  Test: Read orchestrator.md steps 1 and 5
  Status: PASS
  Notes: Step 1 says treat absent/empty as empty map and skip to step 7. Step 5 says "If no key matches, continue (no-op)".

  Criterion: grep returns no flow-specific hardcoded lines
  Test: grep -i "git commit|artifact archiv|PROGRESS.md" orchestrator.md
  Status: PASS
  Notes: All 4 matches are generic executor references or FSM loop infrastructure, not flow-specific hardcoded lines.

  Criterion: FSM loop lines preserved verbatim
  Test: Read orchestrator.md FSM loop section
  Status: PASS
  Notes: State recovery, single-event rule, subagent routing, transition_rules evaluation, STATE.json write, EVENTS.jsonl append all present and intact.
```

### Story S3.1 — Schema validation recognizes transition_actions

```
Story S3.1: Schema validation recognizes transition_actions
  Criterion: validate_flow recognizes transition_actions as known optional key — no unknown-key warning
  Test: validate_flow_cli on team.flow.yaml (which has transition_actions)
  Status: PASS
  Notes: transition_actions in _KNOWN_OPTIONAL_FLOW_KEYS at state.py line 36. Validation exits 0 with no warning.

  Criterion: Validator warns (not errors) when transition_actions absent
  Test: validate_flow_cli on temp YAML without transition_actions key
  Status: PASS
  Notes: Printed warning message and exited 0 (not 1).

  Criterion: Validator errors with clear message when action name not in vocabulary
  Test: validate_flow_cli on temp YAML with type: invalid_action_type
  Status: PASS
  Notes: "Unknown action type 'invalid_action_type'" printed; exited 1.

  Criterion: Validator errors with clear message when FROM->TO not in transitions list
  Test: validate_flow_cli on temp YAML with A->C where only A->B exists
  Status: PASS
  Notes: "transition_actions key 'A->C' does not exist in transitions" printed; exited 1.

  Criterion: state.py loads and exposes transition_actions for orchestrator consumption at runtime
  Test: Call get_transition_actions() with flows with/without the key
  Status: PASS
  Notes: Returns full dict when present, {} when absent or None.
```

### Test infrastructure gap (cross-cutting)

```
  Criterion: Automated tests exist covering transition_actions behavior
  Test: grep -rn "transition_actions" tests/
  Status: NOT COVERED
  Notes: Zero test files reference transition_actions. All verification above was done via
         direct Python invocation and file inspection, not via pytest. A regression could
         land undetected. Recommend adding tests/test_transition_actions.py.

  Criterion: test_orchestrator.py imports and runs successfully
  Test: pytest tests/test_orchestrator.py
  Status: FAIL
  Notes: ImportError: cannot import name 'VALID_STATES' from 'pathly_orchestrator.state'.
         test_orchestrator.py references the old pre-fsm-configurable API. This is a
         pre-existing break, not introduced by fsm-transition-actions, but it blocks
         running any orchestrator-layer automated tests.
```
