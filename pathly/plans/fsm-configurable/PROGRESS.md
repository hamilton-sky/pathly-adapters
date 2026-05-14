# fsm-configurable — Progress

## Status: COMPLETE

## Story Status

| Story | Title | Delivered by | Status |
|---|---|---|---|
| S0.1 | pathly/ root directory consolidates all runtime output | Conv 1 | DONE |
| S1.1 | team.flow.yaml captures the team pipeline FSM | Conv 2 | DONE |
| S1.2 | debug.flow.yaml captures the debug FSM | Conv 2 | DONE |
| S1.3 | explore.flow.yaml captures the explore FSM | Conv 2 | DONE |
| S2.1 | orchestrator.md is a generic FSM engine | Conv 3 | DONE |
| S2.2 | orchestrator.yaml registers flow_config as an input | Conv 3 | DONE |
| S3.1 | team.md passes flow_config when spawning orchestrator | Conv 4 | DONE |
| S3.2 | debug.md spawns the orchestrator instead of running inline | Conv 4 | DONE |
| S3.3 | explore.md spawns the orchestrator instead of running inline | Conv 4 | DONE |
| S3.4 | sub-skills report outcome only; orchestrator owns all state transitions | Conv 4b | DONE |
| S4.1 | pathly-setup materializes flow YAMLs and skill files reference the installed path | Conv 5 | DONE |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|---|---|---|---|---|
| 1 | 0a–0b | S0.1 | DONE | `grep "pathly/plans" src/pathly_data/core/skills/team.md` returns match |
| 2 | 1–3 | S1.1, S1.2, S1.3 | DONE | `git diff --stat` (3 new flow YAML files only) |
| 3 | 4–5 | S2.1, S2.2 | DONE | `git diff --stat` (orchestrator.md + orchestrator YAML) |
| 4 | 6–8 | S3.1, S3.2, S3.3 | DONE | `git diff --stat` (team.md, debug.md, explore.md) |
| 4b | 8a–8c | S3.4 | DONE | `grep "Transition state" team/build.md team/review.md team/test.md` returns no output |
| 5 | 9 | S4.1 | DONE | `grep "materialize_flows" src/install_cli/setup_command.py` returns import + call |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|---|---|---|---|---|---|
| 1 | 0a | `src/pathly_data/core/skills/team.md` | Update feature detection scan from `plans/*/` to `pathly/plans/*/` | grep "pathly/plans" team.md returns match | DONE |
| 1 | 0b | `src/pathly_data/core/agents/orchestrator.md` | Update artifact archiving path from `pipeline-walkthrough/` to `pathly/pipeline-walkthrough/` | grep "pathly/pipeline-walkthrough" orchestrator.md returns match | DONE |
| 2 | 1 | `src/pathly_data/core/flows/team.flow.yaml` | CREATE team FSM config | File exists with storage_path `pathly/plans/{topic}/`, states, transitions, agent_map, feedback_routing | DONE |
| 2 | 2 | `src/pathly_data/core/flows/debug.flow.yaml` | CREATE debug FSM config | File exists with storage_path `pathly/debugs/{topic}/`, states, transitions, agent_map, feedback_routing | DONE |
| 2 | 3 | `src/pathly_data/core/flows/explore.flow.yaml` | CREATE explore FSM config | File exists with storage_path `pathly/explorations/{topic}/`, states, transitions, agent_map, feedback_routing | DONE |
| 3 | 4 | `src/pathly_data/core/agents/orchestrator.md` | Replace hardcoded FSM with flow_config-driven generic engine | No team state literals in logic lines; flow_config read at startup; storage_path from config | DONE |
| 3 | 5 | `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` | Add flow_config + topic input declarations | grep flow_config returns the new field | DONE |
| 3 | 5b | `schemas/state.schema.json` | Remove hardcoded team state enum and transitions block | grep "BUILDING\|RETRO" returns no output; current field uses type:string | DONE |
| 3 | 5c | `src/pathly_orchestrator/state.py`, `eventlog.py` | Generalize state.py (remove VALID_STATES/TRANSITIONS, add load_flow/valid_states/flow_transitions/validate_flow_cli); generalize eventlog.py (storage_path, optional flow validation, backward-compat CLI); add pathly-validate-flow entry point | grep "VALID_STATES\|TRANSITIONS" state.py returns no output; grep "load_flow\|valid_states\|flow_transitions" state.py returns all three; grep "Path(\"plans\")" eventlog.py returns no output; grep "flow: dict" eventlog.py returns both signatures | DONE |
| 4 | 6 | `src/pathly_data/core/skills/team.md` | Add flow_config to orchestrator spawn block | grep flow_config returns src/pathly_data/core/flows/team.flow.yaml | DONE |
| 4 | 7 | `src/pathly_data/core/skills/debug.md` | Replace inline FSM steps with orchestrator spawn | grep orchestrator returns spawn instruction; grep flow_config returns src/pathly_data/core/flows/debug.flow.yaml | DONE |
| 4 | 8 | `src/pathly_data/core/skills/explore.md` | Replace inline spawning with orchestrator spawn | grep orchestrator returns spawn instruction; grep flow_config returns src/pathly_data/core/flows/explore.flow.yaml | DONE |
| 4b | 8a | `src/pathly_data/core/flows/team.flow.yaml` | Add transition_rules section covering BUILDING, REVIEWING, TESTING | grep transition_rules returns new section; grep MORE_CONVS_NEEDED returns match | DONE |
| 4b | 8b | `team/build.md`, `team/review.md`, `team/test.md` | Strip STATE.json transition writes; write-or-delete rule for all transition artifacts | grep "Transition state" all three files returns no output; delete instructions present in review.md and test.md | DONE |
| 4b | 8c | `src/pathly_data/core/agents/orchestrator.md` | Add transition_rules evaluation loop after each sub-agent returns | grep transition_rules and on_artifact returns logic; ownership comment present | DONE |
| 5 | 9 | `src/install_cli/resources.py`, `stitch.py`, `materialize.py`, `setup_command.py` | Materialize flow YAMLs on install; rewrite flow_config paths in stitched skills | grep materialize_flows setup_command.py returns import + call; grep flows_dest stitch.py returns parameter | DONE |

## Prerequisites

- Clean working tree before Conv 1
- `agent-architecture-refactor` Conv 4 DONE before Conv 3 and Conv 4

## Blocked By

- Conv 3 and Conv 4: `agent-architecture-refactor` Conv 4 (team.md thin launcher + orchestrator FSM sections)
- Conv 1 and Conv 2: nothing
