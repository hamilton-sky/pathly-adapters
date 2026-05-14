# orchestrator-skill-delegation — Architecture Proposal

## Problem Statement

The orchestrator's `Execute transition_actions` section implements side-effects inline — running `git` shell commands, editing `PROGRESS.md`, and copying files. This violates the orchestrator's own contract ("Delegate, never implement") and makes transition side-effects untestable in isolation. Adding a new action type (e.g. `notify-slack`) requires changing the orchestrator, not just adding a skill and a YAML line.

## Proposed Solution

Replace inline execution with skill dispatch. The flow YAML's `transition_actions` entries change from `type: <action>` to `skill: <name>`. The orchestrator reads `action.skill` and spawns that skill the same way it spawns FSM agents — by name, passing standardized args. Each skill owns its own guard logic, event appending, and error handling.

## Layer Breakdown

```
Flow YAML  (transition_actions: - skill: commit / - skill: archive-artifacts)
     │  skill name + action args
     ▼
Orchestrator  (Execute transition_actions — 10 lines, pure delegation)
     │  spawn skill(name, topic, storage_path, conv, ...action_fields)
     ▼
commit skill            archive-artifacts skill
  - check feedback        - read feedback/ files
  - git add -A            - copy to artifacts/
  - git commit            - append ACTION_DONE
  - append ACTION_DONE
     │                         │
     ▼                         ▼
Git + Filesystem          Filesystem
```

## Key Design Decisions

### Decision 1: Reuse agent-spawn mechanism for skill dispatch
- **Options considered**: (A) reuse existing agent-spawn pattern, (B) add a new "action runner" concept, (C) keep inline but extract to helper functions
- **Chosen**: A
- **Rationale**: The orchestrator already knows how to spawn a skill by name and wait for it. Adding a second dispatch path (for actions) would complicate the orchestrator. Treating `skill:` dispatch as identical to agent-map dispatch keeps the model simple.

### Decision 2: Guard logic lives in the skill, not the orchestrator
- **Options considered**: (A) skill checks feedback files, (B) orchestrator checks before spawning, (C) both check
- **Chosen**: A
- **Rationale**: The orchestrator's delegation loop should be unconditional — it spawns whatever the YAML says. The commit skill is the right place for "don't commit if there's an open feedback file," because that guard is specific to commit semantics, not to all skills.

### Decision 3: update_progress not extracted in this plan
- **Options considered**: (A) extract all three action types, (B) extract only used ones
- **Chosen**: B
- **Rationale**: `update_progress` has no usages in any current flow YAML. Creating a skill for it now is speculative. Remove it from the orchestrator spec; add `update-progress` skill only when a flow needs it.

## Key Components

| Component | File | Purpose |
|---|---|---|
| `commit` skill | `src/pathly_data/core/skills/commit.md` | Stage + commit with feedback-file guard |
| `archive-artifacts` skill | `src/pathly_data/core/skills/archive-artifacts.md` | Copy feedback files to pipeline-walkthrough/artifacts/ |
| Orchestrator dispatch loop | `src/pathly_data/core/agents/orchestrator.md` | Read `skill:` key, spawn, wait, continue |

## Interface Design

Skills invoked via transition_actions receive these standard args from the orchestrator:
- `topic` — feature/symptom name
- `storage_path` — resolved path for this run (e.g. `pathly/plans/my-feature/`)
- `conv` — current conversation number (from STATE.json)
- Plus any additional fields from the action object (e.g. `message` for commit)

Skills signal completion by appending `ACTION_DONE` to EVENTS.jsonl — same protocol as AGENT_DONE.

## Risks

- **Orchestrator refactor breaks existing team pipeline**: Mitigation — Conv 3 syncs installed files immediately after source changes. Run a team pipeline dry-run after Conv 3 to verify.
- **New skills not installed before orchestrator updated**: Mitigation — Conv ordering enforces skills first (Conv 1), orchestrator second (Conv 2), flows last (Conv 3).
