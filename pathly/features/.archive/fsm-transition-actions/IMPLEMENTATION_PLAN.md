# IMPLEMENTATION_PLAN.md — fsm-transition-actions

_Rigor: lite — 3 conversations, content-inspection verification._

---

## Pre-flight baseline (run before Conversation 1)

Before any implementation begins, run the verify commands below and record any failures as known baseline. Do not attribute pre-existing failures to this feature.

```bash
grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/debug.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/explore.flow.yaml
grep "transition_actions" src/pathly_data/core/agents/orchestrator.md
grep -i "git commit\|artifact archiv\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md
```

Expected baseline: first four greps return no output (key not yet present); fifth grep returns the hardcoded lines that will be removed in Conv 2.

---

## Conversation 1 — Extend flow YAMLs with transition_actions

**Stories delivered:** S1.1, S1.2

**Scope:** Add `transition_actions` to all three flow YAMLs. This is schema-only — orchestrator.md is not touched in this conversation.

**Natural seam:** All three flow YAMLs are updated together so the migration is complete before orchestrator removes its hardcoded logic. The codebase is runnable after this conversation: orchestrator still has the hardcoded side effects, so behavior is unchanged (the new YAML keys are present but not yet read).

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_data/core/flows/team.flow.yaml` | Add `transition_actions` block with `BUILDING->REVIEWING` (git_commit) and `RETRO->DONE` (archive_artifacts) entries |
| `src/pathly_data/core/flows/debug.flow.yaml` | Add `transition_actions` key; minimal content (no mandatory side effects for MVP) |
| `src/pathly_data/core/flows/explore.flow.yaml` | Add `transition_actions` key; minimal content (no mandatory side effects for MVP) |

### team.flow.yaml transition_actions shape

```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - type: git_commit
      message: "feat: complete building stage"
  "RETRO->DONE":
    - type: archive_artifacts
```

### Verify after Conv 1

```bash
grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/debug.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/explore.flow.yaml
grep "BUILDING->REVIEWING" src/pathly_data/core/flows/team.flow.yaml
grep "archive_artifacts" src/pathly_data/core/flows/team.flow.yaml
```

All five greps must return at least one match.

---

## Conversation 2 — Generalize orchestrator.md; remove hardcoded side effects

**Stories delivered:** S2.1

**Scope:** Insert the transition_actions executor into the orchestrator FSM loop; remove the two hardcoded side-effect blocks.

**Natural seam:** Flow YAMLs from Conv 1 already carry the action declarations. After this conversation the codebase is fully wired end-to-end: team/debug/explore behavior is driven by YAML, not orchestrator code. Codebase remains runnable.

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_data/core/agents/orchestrator.md` | Insert transition_actions executor after EVENTS.jsonl append (after line 84); remove autoFlow commits section (lines 125-135); remove artifact archiving section (lines 142-156) |

### Executor insertion point

After the EVENTS.jsonl append step in the FSM loop (currently line 84), insert a section titled `### Execute transition_actions` that:

1. Reads `transition_actions` from the active flow YAML (may be absent — treat as empty map).
2. Constructs the lookup key `"PREV_STATE->NEW_STATE"`.
3. Looks up that key in `transition_actions`; also checks `"->NEW_STATE"` as a wildcard for any transition entering `NEW_STATE`.
4. For each matched action entry (in YAML list order, sequentially):
   - `git_commit`: run `git add -A` then `git commit -m <message>`.
   - `update_progress`: mark the current conv row (if `mark: conv_done`) or all phases (if `mark: all_phases_done`) DONE in PROGRESS.md; orchestrator reads current conv number from STATE.json.
   - `archive_artifacts`: dual-write feedback files to `pipeline-walkthrough/artifacts/`.
5. If no actions match, continue loop (no-op).
6. On action failure: halt and report the failure (match current orchestrator.md halt-and-report behavior for unexpected errors).

### FSM loop preservation constraint

The following must not change: state recovery block, single-event rule, subagent routing, transition_rules evaluation, STATE.json write, EVENTS.jsonl append. These are the lines the architect and upstream features depend on.

### Verify after Conv 2

```bash
grep "transition_actions" src/pathly_data/core/agents/orchestrator.md
grep -i "git commit\|artifact archiv\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md
```

First grep must return at least one match (the executor section). Second grep must return only generic executor references — no flow-specific hardcoded strings (e.g. `"feat: complete building stage"` must not appear in orchestrator.md).

---

## Conversation 3 — Update state.py / validate_flow for transition_actions

**Stories delivered:** S3.1

**BLOCKED — do not begin until:** `fsm-configurable` Phase 5c is DONE and `validate_flow_cli` / `_REQUIRED_FLOW_KEYS` exist in `src/pathly_orchestrator/state.py`.

**Scope:** Extend the Python validation layer to recognize, load, and validate the `transition_actions` optional key.

**Natural seam:** Pure validation addition. No behavior change to orchestrator or flow YAMLs.

### Files to edit

| File | Change |
|------|--------|
| `src/pathly_orchestrator/state.py` | Add `transition_actions` to known optional keys; add validation logic for action names and transition key pairs |

### Validation rules to implement

1. `transition_actions` is optional — warn (do not error) if absent.
2. Each action `type` value must be in `{"git_commit", "update_progress", "archive_artifacts"}` — error on unknown type.
3. Each `FROM->TO` key must reference a pair that exists in the flow's `transitions` list — error if not found.
4. `state.py` must expose `transition_actions` (as a dict or empty dict) for orchestrator consumption.

### Verify after Conv 3

```bash
# With a flow YAML containing a bad action name:
pathly-validate-flow --flow src/pathly_data/core/flows/team.flow.yaml
# Expect: error message mentioning unknown action type

# With team.flow.yaml as-is:
pathly-validate-flow --flow src/pathly_data/core/flows/team.flow.yaml
# Expect: clean pass (or warn-only if transition_actions absent on debug/explore)
```

---

## Overall verify (run after all conversations complete)

```bash
grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/debug.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/explore.flow.yaml
grep "transition_actions" src/pathly_data/core/agents/orchestrator.md
grep -i "git commit\|artifact archiv\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md
```

Pass criteria: first four return matches; fifth returns only generic executor lines — zero flow-specific hardcoded strings.
