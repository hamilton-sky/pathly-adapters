# fsm-configurable — Flow Diagram

## Before this feature: flow-specific logic scattered across files

```
team.md ─────────────────────────────────────────────────────────────┐
  [inline FSM: hardcoded states, routing, storage at plans/<feature>/] │
  └─► spawns orchestrator (post agent-architecture-refactor Conv 4)    │
       [orchestrator still has team-specific state names + routing]    │
                                                                       │
debug.md ──────────────────────────────────────────────────────────── │
  [inline FSM: 6 steps, no STATE.json, no EVENTS.jsonl]               │
  [spawns scout/builder/tester directly per step]                      │
                                                                       │
explore.md ─────────────────────────────────────────────────────────  │
  [inline 3-phase explorer spawning, no STATE.json, no EVENTS.jsonl]  │
                                                                       │
orchestrator.md ─────────────────────────────────────────────────────┘
  [hardcoded: BUILDING/REVIEWING/TESTING/RETRO state names]
  [hardcoded: plans/<feature>/ storage path]
  [hardcoded: ARCH_FEEDBACK → architect, etc.]
```

---

## After this feature: generic FSM engine + declarative flow configs

```
core/flows/
  team.flow.yaml ──────────────┐
  debug.flow.yaml ─────────────┤
  explore.flow.yaml ───────────┤
  (future: audit.flow.yaml, …) ┘
           │
           │  flow_config path
           ▼
team.md ──► Spawn orchestrator(flow_config: team.flow.yaml, topic: …)
debug.md ─► Spawn orchestrator(flow_config: debug.flow.yaml, topic: …)
explore.md► Spawn orchestrator(flow_config: explore.flow.yaml, topic: …)
           │
           ▼
    orchestrator.md  [GENERIC FSM ENGINE]
    ┌──────────────────────────────────────────────────────────────┐
    │ 1. Read flow_config file                                     │
    │ 2. Extract: storage_path, states, transitions,               │
    │             agent_map, feedback_routing                      │
    │ 3. Substitute {topic} into storage_path                      │
    │ 4. Write STATE.json + EVENTS.jsonl to storage_path           │
    │ 5. Loop: current_state → agent_map[current_state] → spawn    │
    │ 6. On feedback file: route per feedback_routing from config  │
    │ 7. On terminal state (DONE): stop                            │
    └──────────────────────────────────────────────────────────────┘
           │
           ├── team run ──► plans/<feature>/STATE.json + EVENTS.jsonl
           ├── debug run ─► debugs/<symptom>/STATE.json + EVENTS.jsonl
           └── explore run► explorations/<topic>/STATE.json + EVENTS.jsonl
```

---

## Flow config schema (all three files share this structure)

```yaml
flow: <name>
storage_path: "<directory>/{topic}/"
states:
  - STATE_A
  - STATE_B
  - …
  - DONE
transitions:
  STATE_A: [STATE_B, BLOCKED_ON_HUMAN]
  STATE_B: [STATE_C, …]
  …
agent_map:
  STATE_A: <agent-or-skill-name>
  STATE_B: <agent-or-skill-name>
  …
feedback_routing:
  FEEDBACK_FILE_NAME: <agent-to-route-to>
  …
```

---

## Conversation sequencing

```
Conv 1 (independent)
  Create core/flows/ directory
  Write team.flow.yaml, debug.flow.yaml, explore.flow.yaml
       │
       │  (agent-architecture-refactor Conv 4 must also complete)
       │
Conv 2 (depends on Conv 1 + agent-architecture-refactor Conv 4)
  Generalize orchestrator.md
  Update orchestrator.yaml (both adapters)
       │
Conv 3 (depends on Conv 2)
  Update team.md, debug.md, explore.md
  Each file spawns orchestrator with its flow_config path
```
