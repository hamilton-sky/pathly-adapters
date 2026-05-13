# fsm-transition-actions — Feature Index

## What this feature is

Extend the flow YAML schema with a `transition_actions` field so that side effects
(git commits, PROGRESS.md updates, artifact archiving) are declared per-flow in YAML
rather than hardcoded in orchestrator.md. Orchestrator becomes a pure FSM engine: it
reads and executes transition actions generically without knowing what any specific flow
does between stages.

## Why it matters

After `fsm-configurable` lands, orchestrator.md is already a generic engine — but it
still contains hardcoded side-effect logic (git commit rules, PROGRESS.md update rules,
artifact archiving rules) that were moved there from team.md. These are team-pipeline
concerns, not FSM-engine concerns. Every new flow type that needs different side effects
would require editing orchestrator.md, which defeats the purpose of the generic engine.

This feature completes the separation: flow YAMLs own their own side effects, orchestrator
owns only state transitions.

## Dependencies (must be DONE before this begins)

- `agent-architecture-refactor` — ALL conversations DONE
- `fsm-configurable` — ALL conversations DONE

Reason: this plan refactors orchestrator.md and flow YAMLs that both upstream plans
create and populate. Working on an incomplete base would cause conflicts.

## Conversation map

| Conv | Scope | Stories |
|------|-------|---------|
| 1 | Extend flow YAML schema + update all three flow YAMLs | S1.1, S1.2 |
| 2 | Generalize orchestrator.md to execute transition_actions; remove hardcoded side effects | S2.1 |
| 3 | Update state.py / validate_flow to require transition_actions key | S3.1 |

## Key file paths

**Flow YAMLs (all three need transition_actions added):**
- `src/pathly_data/core/flows/team.flow.yaml`
- `src/pathly_data/core/flows/debug.flow.yaml`
- `src/pathly_data/core/flows/explore.flow.yaml`

**Orchestrator (side-effect logic gets removed, action executor gets added):**
- `src/pathly_data/core/agents/orchestrator.md`

**Python validation layer (schema must accept new key):**
- `src/pathly_orchestrator/state.py` — `_REQUIRED_FLOW_KEYS` and `validate_flow_cli`

**Reference (already-correct delegation pattern):**
- `src/pathly_data/core/agents/reviewer.md`

## Verify command (run after all conversations complete)

```
grep "transition_actions" src/pathly_data/core/flows/team.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/debug.flow.yaml
grep "transition_actions" src/pathly_data/core/flows/explore.flow.yaml
grep "transition_actions" src/pathly_data/core/agents/orchestrator.md
grep -i "git commit\|artifact archiv\|PROGRESS.md" src/pathly_data/core/agents/orchestrator.md
```

Last grep must return no hardcoded logic lines (only generic "execute transition_actions" instruction).

## No test suite note

Skill and agent `.md` files have no automated tests. Correctness is verified by content
inspection (grep) after each conversation. Flow YAML schema is validated by
`pathly-validate-flow` (added in `fsm-configurable`).
