# fsm-configurable — Progress

## Status: TODO

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S1.1 | team.flow.yaml captures the team pipeline FSM | Conv 1 | TODO |
| S1.2 | debug.flow.yaml captures the debug FSM | Conv 1 | TODO |
| S1.3 | explore.flow.yaml captures the explore FSM | Conv 1 | TODO |
| S2.1 | orchestrator.md is a generic FSM engine | Conv 2 | TODO |
| S2.2 | orchestrator.yaml registers flow_config as an input | Conv 2 | TODO |
| S3.1 | team.md passes flow_config when spawning orchestrator | Conv 3 | TODO |
| S3.2 | debug.md spawns the orchestrator instead of running inline | Conv 3 | TODO |
| S3.3 | explore.md spawns the orchestrator instead of running inline | Conv 3 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 1–3 | S1.1, S1.2, S1.3 | TODO | `git diff --stat` (3 new flow YAML files only) |
| 2 | 4–5 | S2.1, S2.2 | TODO | `git diff --stat` (orchestrator.md + orchestrator YAML) |
| 3 | 6–8 | S3.1, S3.2, S3.3 | TODO | `git diff --stat` (team.md, debug.md, explore.md) |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 1 | `src/pathly_data/core/flows/team.flow.yaml` | CREATE team FSM config | File exists with storage_path, states, transitions, agent_map, feedback_routing | TODO |
| 1 | 2 | `src/pathly_data/core/flows/debug.flow.yaml` | CREATE debug FSM config | File exists with storage_path, states, transitions, agent_map, feedback_routing | TODO |
| 1 | 3 | `src/pathly_data/core/flows/explore.flow.yaml` | CREATE explore FSM config | File exists with storage_path, states, transitions, agent_map, feedback_routing | TODO |
| 2 | 4 | `src/pathly_data/core/agents/orchestrator.md` | Replace hardcoded FSM with flow_config-driven generic engine | No team state literals in logic lines; flow_config read at startup; storage_path from config | TODO |
| 2 | 5 | `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` | Add flow_config + topic input declarations | grep flow_config returns the new field | TODO |
| 3 | 6 | `src/pathly_data/core/skills/team.md` | Add flow_config to orchestrator spawn block | grep flow_config returns core/flows/team.flow.yaml | TODO |
| 3 | 7 | `src/pathly_data/core/skills/debug.md` | Replace inline FSM steps with orchestrator spawn | grep orchestrator returns spawn instruction; grep flow_config returns core/flows/debug.flow.yaml | TODO |
| 3 | 8 | `src/pathly_data/core/skills/explore.md` | Replace inline spawning with orchestrator spawn | grep orchestrator returns spawn instruction; grep flow_config returns core/flows/explore.flow.yaml | TODO |

## Prerequisites

- Clean working tree before Conv 1
- `agent-architecture-refactor` Conv 4 DONE before Conv 2 and Conv 3

## Blocked By

- Conv 2 and Conv 3: `agent-architecture-refactor` Conv 4 (team.md thin launcher + orchestrator FSM sections)
- Conv 1: nothing
