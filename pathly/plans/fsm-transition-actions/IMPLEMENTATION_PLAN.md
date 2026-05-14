# fsm-transition-actions — Implementation Plan

## Overview

This plan refactors the orchestrator to move hardcoded side-effect logic (git commits, PROGRESS.md updates, artifact archiving) from orchestrator.md into per-flow YAML declarations. The orchestrator becomes a pure FSM engine with a fixed vocabulary of transition actions it can execute.

## Scope (3 conversations)

| Conv | Owner | Stories | Acceptance Criteria |
|------|-------|---------|-------------------|
| 1 | builder | S1.1, S1.2 | All three flow YAMLs have `transition_actions` key populated with all required actions; schema is valid |
| 2 | builder | S2.1 | Orchestrator reads and executes transition_actions generically; all hardcoded side-effect code removed; existing flows still work |
| 3 | builder | S3.1 | state.py validates new key; pathly-validate-flow requires transition_actions in strict mode, warns in lite |

## Conversation 1 — Extend flow YAML schema

### Story 1.1: Add transition_actions to team.flow.yaml

**Input files:**
- `src/pathly_data/core/flows/team.flow.yaml` (current)
- Reference: ARCHITECTURE_PROPOSAL.md (target schema)

**Output:** Updated team.flow.yaml with transition_actions key

**Tasks:**
1. Add `transition_actions` key after `transition_rules` in team.flow.yaml
2. Populate transitions with action declarations:
   - `"BUILDING->REVIEWING"` → `[{type: git_commit, message: "feat(<topic>): building complete"}]`
   - `"REVIEWING->TESTING"` → `[{type: update_progress, mark: conv_done}, {type: git_commit, message: "chore: review passed, tests starting"}]`
   - `"TESTING->RETRO"` → `[{type: update_progress, mark: all_phases_done}, {type: git_commit, message: "chore: tests passed"}]`
   - `"->DONE"` → `[{type: archive_artifacts}]`
3. Validate YAML syntax
4. Run pathly-validate-flow (if it exists) to check schema compliance

**Definition of Done:**
- team.flow.yaml parses without errors
- All action types use only vocabulary from ARCHITECTURE_PROPOSAL.md
- Commit messages match current hardcoded messages in orchestrator.md
- All four transition paths listed above are present

### Story 1.2: Add transition_actions to debug.flow.yaml and explore.flow.yaml

**Input files:**
- `src/pathly_data/core/flows/debug.flow.yaml`
- `src/pathly_data/core/flows/explore.flow.yaml`

**Output:** Updated debug and explore flow YAMLs with transition_actions keys

**Tasks:**
1. For each flow, identify all state transitions from `transitions` and `transition_rules`
2. Add `transition_actions` key
3. For transitions that are architecture-shared (BUILDING→REVIEWING, TESTING→RETRO, →DONE):
   - Use same action structure as team.flow.yaml
4. For flow-specific transitions:
   - debug flow may have different commit messages (e.g., "chore(debug): testing complete")
   - explore flow may skip git_commit actions entirely (read-only?)
5. Validate syntax for both files

**Definition of Done:**
- Both files parse without errors
- transition_actions is declared for all state-changing transitions
- Commit messages are specific to flow purpose if needed

## Conversation 2 — Generalize orchestrator.md to execute transition_actions

### Story 2.1: Refactor orchestrator to be a pure FSM engine

**Input files:**
- `src/pathly_data/core/agents/orchestrator.md` (current — contains hardcoded side effects)
- Updated flow YAMLs from Conv 1
- Reference: orchestrator.md Guard statements for context

**Output:** Updated orchestrator.md with side effects removed, action executor added

**Changes:**

1. **Remove hardcoded side effects:**
   - Delete: autoFlow commit logic (lines ~130-135 in current orchestrator.md)
   - Delete: PROGRESS.md update logic (any code that marks conv or phase done)
   - Delete: artifact archiving logic (any code that copies feedback files to pipeline-walkthrough/)
   - Verify: grep "git add\|git commit\|PROGRESS.md\|pipeline-walkthrough" returns no results after refactor

2. **Add transition action executor:**
   - After FSM determines `next_state` and writes STATE.json/EVENTS.jsonl
   - Before looping to next iteration: check if `transition_actions["FROM->TO"]` exists in loaded flow config
   - If match found: execute each action in order
   - Supported actions:
     - `git_commit`: Run `git add -A && git commit -m "<message>"` with autoFlow condition
     - `update_progress`: Call update_progress_helper with mark parameter (conv_done / all_phases_done)
     - `archive_artifacts`: Call archive_artifacts_helper to dual-write feedback files
   - Unknown actions: log warning and skip (fail-safe)

3. **Helper functions (inline in orchestrator.md):**
   - `execute_git_commit(message, autoFlow)`: Only runs if autoFlow=true
   - `update_progress_helper(mark)`: Find PROGRESS.md, update based on mark type
   - `archive_artifacts_helper()`: Scan feedback/ dir, dual-write to pipeline-walkthrough/artifacts/

**Testing approach:**
- Manual: Run /pathly-team fsm-transition-actions build after this change
  - Observe: IMPLEMENTATION_PLAN.md exists (artifact from Conv 1)
  - Expected: orchestrator executes PLANNING→BUILDING transition
  - Check: No new side effects should fire (transition_actions not populated in team.flow.yaml yet)
  - Verify: STATE.json updates correctly; no commit is made (no transition_actions for PLANNING→BUILDING)
- After Conv 1 completes: Re-run /pathly-team fsm-transition-actions build with full team.flow.yaml
  - Expected: autoFlow commits now fire for BUILDING→REVIEWING transition
  - Verify: git log shows new commit with "feat(fsm-transition-actions): building complete"

**Definition of Done:**
- Orchestrator.md has no hardcoded side-effect logic
- transition_actions executor is implemented and documented
- All 3 action types work: git_commit, update_progress, archive_artifacts
- FSM loop behavior unchanged for state transitions and feedback routing
- Existing tests (if any) still pass

## Conversation 3 — Update validation layer

### Story 3.1: Update state.py to validate transition_actions key

**Input files:**
- `src/pathly_orchestrator/state.py` (current)
- Updated flow YAMLs from Conv 1

**Output:** Updated state.py with transition_actions validation

**Tasks:**

1. **Identify validation points:**
   - `_REQUIRED_FLOW_KEYS`: List of keys that must be present in all flow YAMLs
   - `validate_flow_cli`: Command-line validation entrypoint

2. **Add transition_actions to validation:**
   - In lite/standard scope: transition_actions is optional (flows with no side effects allowed)
   - In strict scope: transition_actions is required if any transitions exist
   - Validate action type against fixed vocabulary: git_commit, update_progress, archive_artifacts
   - Validate transition key format: "FROM->TO" or "->STATE" (wildcard)

3. **Update pathly-validate-flow warning/error:**
   - Lite: Warn if transition_actions is missing (flow works but may miss side effects)
   - Standard: Same as lite
   - Strict: Error if transition_actions is missing

4. **Test validation:**
   - Run pathly-validate-flow on all three updated flow YAMLs
   - Verify: No schema errors
   - Verify: Warning/error levels match scope

**Definition of Done:**
- state.py accepts transition_actions key in all three flow YAMLs
- pathly-validate-flow passes without errors on updated files
- validation rules match lite/standard/strict scopes documented in orchestrator.md

## File change summary

### Files modified:
- `src/pathly_data/core/flows/team.flow.yaml` — Add transition_actions key (Conv 1.1)
- `src/pathly_data/core/flows/debug.flow.yaml` — Add transition_actions key (Conv 1.2)
- `src/pathly_data/core/flows/explore.flow.yaml` — Add transition_actions key (Conv 1.2)
- `src/pathly_data/core/agents/orchestrator.md` — Remove hardcoded side effects, add action executor (Conv 2.1)
- `src/pathly_orchestrator/state.py` — Add transition_actions validation (Conv 3.1)

### Files created:
- None (all changes are in existing files)

### Files deleted:
- None

## Verification command (run after ALL conversations complete)

```bash
# Verify transition_actions is present in all flow YAMLs
grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml || echo "FAIL: team.flow.yaml"
grep "transition_actions" src/pathly_data/core/flows/debug.flow.yaml || echo "FAIL: debug.flow.yaml"
grep "transition_actions" src/pathly_data/core/flows/explore.flow.yaml || echo "FAIL: explore.flow.yaml"

# Verify no hardcoded side effects remain in orchestrator.md
if grep -E "git add|git commit|PROGRESS\.md|pipeline-walkthrough" src/pathly_data/core/agents/orchestrator.md; then
  echo "FAIL: Hardcoded side effects still in orchestrator.md"
else
  echo "PASS: No hardcoded side effects"
fi

# Verify transition_actions execution is documented
grep -q "transition_actions executor\|execute_git_commit\|update_progress_helper\|archive_artifacts_helper" src/pathly_data/core/agents/orchestrator.md && echo "PASS: Action executor documented"

# Validate all flow YAMLs
pathly-validate-flow src/pathly_data/core/flows/team.flow.yaml
pathly-validate-flow src/pathly_data/core/flows/debug.flow.yaml
pathly-validate-flow src/pathly_data/core/flows/explore.flow.yaml
```

## Dependencies and risks

**Dependencies:** Assumes fsm-configurable has landed and orchestrator.md exists with current side-effect logic.

**Risks:**
1. **Breaking change if flows omit transition_actions:** Mitigated by making transition_actions optional in lite/standard, required only in strict
2. **Commit message format changes:** All messages must match current git log conventions; builder review catches this
3. **PROGRESS.md update logic changes:** Existing conv/phase marking must work identically; tester review catches regressions

## Notes for builder

- The ARCHITECTURE_PROPOSAL.md and FEATURE_INDEX.md contain the design decisions; refer to them for questions about action vocabulary and transition key format.
- After Conv 1, the FSM can enter PLANNING→BUILDING transition. This is low-risk because Conv 2 has not yet run, so no transition actions will fire.
- After Conv 2, existing flows inherit new side-effect behavior. Carefully verify TESTING→RETRO and →DONE transitions work correctly.
- Conv 3 is validation-only and has no FSM impact.

## Manual test after implementation

```bash
# Set up a small test feature
/pathly-team test-transition-actions plan

# Build a simple change
/pathly-team test-transition-actions build  # should produce IMPLEMENTATION_PLAN + code

# If autoFlow enabled, should see:
# 1. BUILDING→REVIEWING transition (no git commit expected in Conv 2, only in Conv 1+2 together)
# 2. After reviewer approval, REVIEWING→TESTING transition (should see git commit in log)
# 3. After tests pass, TESTING→RETRO (should see git commit + PROGRESS.md update)

# Verify state machine correctness
cat pathly/plans/test-transition-actions/STATE.json
cat pathly/plans/test-transition-actions/EVENTS.jsonl
```
