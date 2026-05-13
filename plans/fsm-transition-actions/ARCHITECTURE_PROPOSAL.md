# fsm-transition-actions — Architecture Proposal

## Current state (after fsm-configurable lands)

Orchestrator.md is a generic FSM engine — states, transitions, agent_map, and
feedback_routing all come from the flow YAML. However, transition side effects are
still hardcoded inside orchestrator.md:

```
After BUILDING → REVIEWING (autoFlow):
  git add -A
  git commit -m "feat: complete building stage"

After TESTING → RETRO (tests passed):
  update PROGRESS.md — mark conv row DONE
  git commit -m "chore: tests passed"

After DONE:
  copy feedback files to pipeline-walkthrough/.../artifacts/
```

This means:
- orchestrator.md must be edited whenever a flow needs different side effects
- debug and explore flows inherit team-pipeline commit semantics (wrong)
- orchestrator.md violates SRP: it is both an FSM engine and a team-pipeline side-effect handler

## Target state

Side effects move into each flow YAML under a `transition_actions` key. Orchestrator
reads and executes them generically — it has no knowledge of what any specific action does
beyond a fixed vocabulary of action types.

### Extended flow YAML schema

```yaml
transition_actions:
  "BUILDING->REVIEWING":
    - type: git_commit
      message: "feat: complete building stage"
  "REVIEWING->TESTING":
    - type: update_progress
      mark: conv_done
    - type: git_commit
      message: "chore: review passed, tests starting"
  "TESTING->RETRO":
    - type: update_progress
      mark: all_phases_done
    - type: git_commit
      message: "chore: tests passed"
  "->DONE":
    - type: archive_artifacts
```

Keys are `"FROM->TO"` transition strings. `"->DONE"` is a wildcard matching any
transition that lands in DONE. Actions are executed in order.

### Action vocabulary (fixed, implemented in orchestrator.md)

| type | Description |
|------|-------------|
| `git_commit` | `git add -A` then `git commit -m <message>` |
| `update_progress` | Mark current conv or all phases DONE in PROGRESS.md |
| `archive_artifacts` | Dual-write feedback files to pipeline-walkthrough artifacts |

New action types require updating orchestrator.md (intentionally limited vocabulary).
New flows only need to use existing action types — no orchestrator changes required.

### Orchestrator.md after refactor

Orchestrator becomes ~150 lines:

1. **Startup** — read flow_config, validate required keys, substitute {topic}
2. **State recovery** — read STATE.json, determine entry stage
3. **FSM loop** — for each iteration: read current state → look up agent_map → spawn
   sub-agent → read result → determine next state → execute transition_actions for
   this transition → write new STATE.json → loop
4. **BLOCKED_ON_HUMAN** — print, wait, restore state on resume
5. **Hard constraints** — what orchestrator must never do

No team-specific state names, no hardcoded commit messages, no PROGRESS.md paths.

## Why not keep side effects in sub-skills

The sub-skill (e.g. team/build.md) finishes work and returns. The *orchestrator* is
the entity that knows:
- that the transition BUILDING→REVIEWING just succeeded
- what the autoFlow setting is
- whether to commit or wait

Side effects belong on the transition, not inside the sub-agent. Sub-agents report
outcomes; the FSM decides what happens next and what side effects fire. This is the
standard FSM model (Moore vs Mealy machines — transition actions are Mealy outputs).

## Design decisions

- **Transition key format `"FROM->TO"`** — explicit, grep-verifiable, no ambiguity about
  when an action fires. Wildcard `"->STATE"` covers "entering STATE from anywhere."
- **Fixed action vocabulary** — prevents flow YAMLs from embedding arbitrary shell
  commands. New action types require a deliberate orchestrator.md edit.
- **`transition_actions` is optional in schema** — flows with no side effects (e.g. a
  future read-only audit flow) do not need the key. `_validate_flows` should not require
  it; `pathly-validate-flow` warns but does not error if absent.
- **`update_progress` marks by convention** — `mark: conv_done` finds the current
  conversation row; `mark: all_phases_done` marks every phase in the current conv.
  Orchestrator knows the current conv number from STATE.json.
