# CONVERSATION_PROMPTS.md — fsm-transition-actions

_Ready-to-paste prompts. Run each conversation to completion before starting the next._
_Conv 3 is blocked — do not paste until fsm-configurable Phase 5c is DONE._

---

## Conversation 1 — Extend flow YAMLs with transition_actions

**Stories:** S1.1, S1.2

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: fsm-transition-actions
Conversation: 1 of 3
Stories: S1.1, S1.2 — Declarative transition_actions in flow YAML schema

## Context

The orchestrator currently hardcodes side effects (git commits, artifact archiving) for
the team pipeline. This feature moves those declarations into each flow YAML under a new
`transition_actions` key. This conversation adds the key to all three existing flow YAMLs.
Orchestrator.md is NOT touched in this conversation.

## Files to edit

src/pathly_data/core/flows/team.flow.yaml
src/pathly_data/core/flows/debug.flow.yaml
src/pathly_data/core/flows/explore.flow.yaml

## What to add

### team.flow.yaml

Add a top-level `transition_actions` key with the following structure (add after the
existing top-level keys, before any trailing whitespace):

  transition_actions:
    "BUILDING->REVIEWING":
      - type: git_commit
        message: "feat: complete building stage"
    "RETRO->DONE":
      - type: archive_artifacts

### debug.flow.yaml

Add a top-level `transition_actions` key with an empty mapping (no side effects for MVP):

  transition_actions: {}

### explore.flow.yaml

Add a top-level `transition_actions` key with an empty mapping (no side effects for MVP):

  transition_actions: {}

## Constraints

- Every FROM->TO key must reference a transition pair that exists in that flow's
  `transitions` list. Verify before committing.
- Action type values must be from: git_commit, update_progress, archive_artifacts.
- Do not change any existing keys in any flow YAML.
- Do not touch orchestrator.md.

## Verify after completion

Run these commands and confirm each returns at least one match:

  grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml
  grep "transition_actions" src/pathly_data/core/flows/debug.flow.yaml
  grep "transition_actions" src/pathly_data/core/flows/explore.flow.yaml
  grep "BUILDING->REVIEWING" src/pathly_data/core/flows/team.flow.yaml
  grep "archive_artifacts" src/pathly_data/core/flows/team.flow.yaml
```

---

## Conversation 2 — Generalize orchestrator.md; remove hardcoded side effects

**Stories:** S2.1

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: fsm-transition-actions
Conversation: 2 of 3
Story: S2.1 — Orchestrator executes transition_actions generically

## Prerequisite

Conversation 1 must be complete. Verify:
  grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml
This must return at least one match before proceeding.

## Context

The flow YAMLs now declare transition_actions. Orchestrator.md must be updated to:
1. Execute those actions generically after each FSM transition.
2. Remove the two hardcoded side-effect blocks that transition_actions replaces.

## File to edit

src/pathly_data/core/agents/orchestrator.md

## Read the file first

Read orchestrator.md in full before making any edits. Pay attention to:
- The FSM loop (state recovery, single-event rule, subagent routing, transition_rules
  evaluation, STATE.json write, EVENTS.jsonl append). These lines must be preserved verbatim.
- The autoFlow commits section (around lines 125-135) — this will be REMOVED.
- The artifact archiving section (around lines 142-156) — this will be REMOVED.

## Change 1 — Insert transition_actions executor

After the EVENTS.jsonl append step in the FSM loop, insert a new section titled
`### Execute transition_actions`. This section must:

1. Read `transition_actions` from the active flow YAML. If the key is absent or empty,
   treat as an empty map and continue (no-op).
2. Construct the lookup key as `"PREV_STATE->NEW_STATE"` using the state values from
   this iteration's transition.
3. Look up that key in `transition_actions`. Also check `"->NEW_STATE"` as a wildcard
   for any transition that lands in NEW_STATE.
4. For each matched action in YAML list order (sequential, not parallel):
   - git_commit: run `git add -A` then `git commit -m <message>`.
   - update_progress: if mark is `conv_done`, mark the current conversation row DONE in
     PROGRESS.md (orchestrator reads current conv number from STATE.json); if mark is
     `all_phases_done`, mark every phase in the current conversation DONE.
   - archive_artifacts: dual-write feedback files to pipeline-walkthrough/artifacts/.
5. If no key matches, continue the loop (no-op).
6. On action failure: halt and surface the error (same halt-and-report behavior as other
   unexpected errors in the loop).

## Change 2 — Remove hardcoded autoFlow commits section

Remove the `### autoFlow commits` section (approximately lines 125-135) that contains
hardcoded `git add -A && git commit` instructions. This logic now lives in team.flow.yaml.

## Change 3 — Remove hardcoded artifact archiving section

Remove the artifact archiving dual-write section (approximately lines 142-156).
This logic now lives in team.flow.yaml as the archive_artifacts action on RETRO->DONE.

## Constraints

- The FSM loop lines (state recovery, single-event rule, subagent routing,
  transition_rules evaluation, STATE.json write, EVENTS.jsonl append) must not change.
- Do not touch any flow YAML files.
- Do not add any team-specific or flow-specific logic to orchestrator.md.

## Verify after completion

  grep "transition_actions" src/pathly_data/core/agents/orchestrator.md
  grep -i "git commit\|artifact archiv\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md

First grep must return at least one match (the executor section).
Second grep must return only generic executor references — no hardcoded commit messages
(e.g. "feat: complete building stage" must not appear in orchestrator.md).
```

---

## Conversation 3 — Update state.py / validate_flow for transition_actions

**Stories:** S3.1

**BLOCKED — do not paste until fsm-configurable Phase 5c is DONE.**

Check: `_REQUIRED_FLOW_KEYS` and `validate_flow_cli` must exist in
`src/pathly_orchestrator/state.py` before starting.

```
You are a builder. Do not ask clarifying questions — implement exactly what is described.

Feature: fsm-transition-actions
Conversation: 3 of 3
Story: S3.1 — Schema validation for transition_actions

## Prerequisite

fsm-configurable Phase 5c must be complete. Verify before starting:
  grep "_REQUIRED_FLOW_KEYS" src/pathly_orchestrator/state.py
  grep "validate_flow_cli" src/pathly_orchestrator/state.py
Both must return at least one match.

## File to edit

src/pathly_orchestrator/state.py

## Read the file first

Read state.py in full before making any edits. Identify:
- Where `_REQUIRED_FLOW_KEYS` is defined.
- Where `validate_flow_cli` performs its validation logic.
- Where flow data is loaded and returned for orchestrator consumption.

## Changes to make

### 1. Register transition_actions as a known optional key

Add `transition_actions` to the set of known optional top-level flow YAML keys so the
validator does not warn about it being unrecognized.

### 2. Add warning for absent transition_actions

In `validate_flow_cli`: if a loaded flow YAML does not contain `transition_actions`,
emit a warning (do not error). Example warning text:
  "transition_actions key absent — flow has no declared side effects"

### 3. Validate action type names

In `validate_flow_cli`: if `transition_actions` is present, iterate each action entry.
Error with a clear message if `type` is not in
`{"git_commit", "update_progress", "archive_artifacts"}`.
Example error text:
  "Unknown action type '<value>' in transition_actions[<key>]"

### 4. Validate transition key pairs

In `validate_flow_cli`: for each `FROM->TO` key in `transition_actions`, verify that the
pair exists in the flow's `transitions` list. Error with a clear message if not found.
Example error text:
  "transition_actions key '<FROM->TO>' does not exist in transitions"

### 5. Expose transition_actions for orchestrator consumption

Ensure the function or method that loads flow data returns `transition_actions` as a
dict (or empty dict `{}` if absent) so the orchestrator can consume it at runtime.

## Constraints

- `transition_actions` remains optional — absence is a warning, not an error.
- Do not change the required-key validation for keys that fsm-configurable defined.
- Do not edit orchestrator.md or any flow YAML.

## Verify after completion

  # With team.flow.yaml (has valid transition_actions):
  pathly-validate-flow --flow src/pathly_data/core/flows/team.flow.yaml
  # Expected: clean pass

  # Manually introduce an invalid action type in a temp copy of team.flow.yaml,
  # then run validate-flow against it:
  # Expected: error message containing "Unknown action type"

  # With debug.flow.yaml (has empty transition_actions {}):
  pathly-validate-flow --flow src/pathly_data/core/flows/debug.flow.yaml
  # Expected: clean pass (empty mapping is valid)
```
