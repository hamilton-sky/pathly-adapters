# fsm-configurable — User Stories

## Context

The pathly orchestrator is hardcoded to the team pipeline: fixed state names (BUILDING, REVIEWING, TESTING, RETRO), fixed agent_map, fixed feedback routing, and hardcoded storage at `plans/<feature>/`. Other flows (debug, explore) either run inline with no state tracking or duplicate similar patterns. Runtime output directories (`plans/`, `debugs/`, `explorations/`, `pipeline-walkthrough/`, `lessons/`) are scattered at the project root.

This feature consolidates all runtime output under a `pathly/` root, extracts all flow-specific configuration into `core/flows/*.flow.yaml` files, and rewrites the orchestrator to be a generic FSM engine driven by whichever flow config it receives at spawn time.

---

## Stories

### Story 0.1: pathly/ root directory consolidates all runtime output
**As a** user running any pathly flow, **I want** all runtime output (plans, debug sessions, explorations, pipeline walkthroughs, and lessons) to live under a single `pathly/` directory, **so that** my project root stays clean and all pathly artifacts are in one predictable place.

**Acceptance Criteria:**
- [ ] `team.md` feature detection scans `pathly/plans/*/STATE.json` (not `plans/*/STATE.json`)
- [ ] `orchestrator.md` artifact archiving writes pipeline walkthroughs to `pathly/pipeline-walkthrough/<feature>/artifacts/`
- [ ] All flow config `storage_path` fields use `pathly/` prefix (`pathly/plans/{topic}/`, `pathly/debugs/{topic}/`, `pathly/explorations/{topic}/`)
- [ ] `lessons.md` skill writes and reads from `pathly/lessons/LESSONS_CANDIDATE.md` and `pathly/lessons/LESSONS.md`
- [ ] `retro.md` skill appends lessons to `pathly/lessons/LESSONS_CANDIDATE.md` (not `lessons/LESSONS_CANDIDATE.md`)

**Delivered by:** Phase 0a–0b → Conversation 1

---

### Story 1.1: team.flow.yaml captures the team pipeline FSM
**As a** contributor adding a new pipeline stage, **I want** the team FSM to be defined in a YAML file, **so that** I can read one file to understand the full state machine without reading orchestrator.md.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/flows/team.flow.yaml` exists
- [ ] The file declares all team pipeline states: IDLE, STORMING, PLANNING, BUILDING, REVIEWING, TESTING, RETRO, BLOCKED_ON_HUMAN, DONE
- [ ] The file declares all valid transitions between those states
- [ ] The file declares an `agent_map` mapping each state to the agent or skill to invoke
- [ ] The file declares `storage_path: pathly/plans/{topic}/`
- [ ] The file declares `feedback_routing` covering ARCH_FEEDBACK, REVIEW_FAILURES, TEST_FAILURES, IMPL_QUESTIONS, DESIGN_QUESTIONS, HUMAN_QUESTIONS

**Delivered by:** Phase 1 → Conversation 2

---

### Story 1.2: debug.flow.yaml captures the debug FSM
**As a** contributor, **I want** the debug flow states and routing to be declared in YAML, **so that** debug runs gain STATE.json + EVENTS.jsonl tracking identical to team pipeline runs.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/flows/debug.flow.yaml` exists
- [ ] The file declares states: INVESTIGATING, REPRODUCING, ROOT_CAUSE_FOUND, FIXING, VERIFYING, DONE
- [ ] The file declares valid transitions between those states
- [ ] The file declares an `agent_map` mapping each state to the appropriate agent to invoke
- [ ] The file declares `storage_path: pathly/debugs/{topic}/`
- [ ] The file declares `feedback_routing` covering TEST_FAILURES and HUMAN_QUESTIONS at minimum

**Delivered by:** Phase 2 → Conversation 2

---

### Story 1.3: explore.flow.yaml captures the explore FSM
**As a** contributor, **I want** the explore flow states and routing to be declared in YAML, **so that** exploration runs gain STATE.json + EVENTS.jsonl tracking identical to team pipeline runs.

**Acceptance Criteria:**
- [ ] `src/pathly_data/core/flows/explore.flow.yaml` exists
- [ ] The file declares states: FRAMING, ANALYZING, TRACING, CONCLUDING, DONE
- [ ] The file declares valid transitions between those states
- [ ] The file declares an `agent_map` mapping each state to the appropriate agent to invoke
- [ ] The file declares `storage_path: pathly/explorations/{topic}/`
- [ ] The file declares `feedback_routing` covering HUMAN_QUESTIONS at minimum

**Delivered by:** Phase 3 → Conversation 2

---

### Story 2.1: orchestrator.md is a generic FSM engine
**As a** flow author, **I want** the orchestrator to accept a `flow_config` path at spawn time, **so that** I can create new orchestrated flows without modifying the orchestrator.

**Acceptance Criteria:**
- [ ] `orchestrator.md` reads `flow_config` from its spawn prompt inputs
- [ ] `orchestrator.md` reads `storage_path` from the loaded flow config (not hardcoded to `plans/`)
- [ ] `orchestrator.md` reads the state list and valid transitions from the loaded flow config
- [ ] `orchestrator.md` reads the `agent_map` from the loaded flow config to determine which agent/skill to invoke per state
- [ ] `orchestrator.md` reads `feedback_routing` from the loaded flow config (no hardcoded routing entries remain)
- [ ] `orchestrator.md` contains no literal references to team-specific state names (BUILDING, REVIEWING, TESTING, RETRO) outside of comments
- [ ] `orchestrator.md` writes STATE.json and EVENTS.jsonl to the `storage_path` from the flow config

**Delivered by:** Phase 4 → Conversation 3

---

### Story 2.2: orchestrator.yaml registers flow_config as an input
**As a** host adapter author, **I want** the orchestrator YAML to declare `flow_config` as an accepted input, **so that** the adapter knows what to pass at spawn time.

**Acceptance Criteria:**
- [ ] `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` contains a `flow_config` input field or parameter declaration
- [ ] The codex adapter orchestrator.yaml (if it exists) contains the same `flow_config` declaration

**Delivered by:** Phase 5 → Conversation 3

---

### Story 2.3: state.py and eventlog.py validate against flow config at runtime
**As a** contributor adding a new flow, **I want** the Python validation layer to load valid states and transitions from the flow YAML at runtime, **so that** debug and explore flows are validated correctly and the hardcoded team-pipeline state list no longer blocks new flows.

**Acceptance Criteria:**
- [ ] `state.py` exposes `load_flow(yaml_path)`, `valid_states(flow)`, and `flow_transitions(flow)` functions
- [ ] `state.py` does not define `VALID_STATES`, `STATES`, or `TRANSITIONS`
- [ ] `write_state()` in `eventlog.py` accepts an optional `flow` parameter; when provided, validates `current` against `valid_states(flow)` and validates the transition against `flow_transitions(flow)`; when `None`, skips validation
- [ ] `append_event()` in `eventlog.py` accepts the same optional `flow` parameter with the same guard behavior
- [ ] `eventlog.py` accepts a full storage path (e.g. `pathly/plans/auth-rewrite`) instead of a bare feature name, removing the hardcoded `Path("plans")` prefix
- [ ] CLI command `pathly-state pathly/plans/<feature>` resolves correctly after the `pathly/` migration

**Delivered by:** Phase 5c → Conversation 3

---

### Story 3.1: team.md passes flow_config when spawning orchestrator
**As a** user running the team pipeline, **I want** team.md to pass the team flow config path to the orchestrator, **so that** the orchestrator uses the correct FSM without any team-specific logic embedded in it.

**Acceptance Criteria:**
- [ ] `team.md` spawn instruction for orchestrator includes `flow_config: src/pathly_data/core/flows/team.flow.yaml`
- [ ] `team.md` does not contain hardcoded team state names (BUILDING, REVIEWING, etc.) in the orchestrator spawn block

**Delivered by:** Phase 6 → Conversation 4

---

### Story 3.2: debug.md spawns the orchestrator instead of running inline
**As a** user running a debug session, **I want** debug.md to delegate to the orchestrator, **so that** debug sessions produce STATE.json and EVENTS.jsonl tracking identical to team pipeline runs.

**Acceptance Criteria:**
- [ ] `debug.md` contains a `Spawn **orchestrator** agent` instruction
- [ ] The spawn instruction passes `flow_config: src/pathly_data/core/flows/debug.flow.yaml` and `topic: <symptom-name>`
- [ ] `debug.md` does not contain inline FSM state-transition logic (the six explicit step-to-state mapping)
- [ ] A debug run produces STATE.json and EVENTS.jsonl under `pathly/debugs/<symptom-name>/`

**Delivered by:** Phase 7 → Conversation 4

---

### Story 3.3: explore.md spawns the orchestrator instead of running inline
**As a** user running an exploration, **I want** explore.md to delegate to the orchestrator, **so that** explorations produce STATE.json and EVENTS.jsonl tracking identical to team pipeline runs.

**Acceptance Criteria:**
- [ ] `explore.md` contains a `Spawn **orchestrator** agent` instruction
- [ ] The spawn instruction passes `flow_config: src/pathly_data/core/flows/explore.flow.yaml` and `topic: <topic>`
- [ ] `explore.md` does not contain inline FSM state-transition logic
- [ ] An explore run produces STATE.json and EVENTS.jsonl under `pathly/explorations/<topic>/`

**Delivered by:** Phase 8 → Conversation 4

---

### Story 3.4: sub-skills report outcome only — orchestrator owns all state transitions
**As a** flow author, **I want** team sub-skills (build, review, test) to write artifacts only and never write STATE.json transitions, **so that** the orchestrator is the single entity that controls the FSM state and routing decisions are not duplicated between skills and the engine.

**Acceptance Criteria:**
- [ ] `team/build.md` does not contain `Transition state` or `STATE.json` write instructions for `current`
- [ ] `team/review.md` does not contain routing logic (`if more TODO → BUILDING, else → TESTING`); instead writes `MORE_CONVS_NEEDED.md` if more conversations remain
- [ ] `team/review.md` does not write `current` to STATE.json
- [ ] `team/test.md` does not contain `Transition state → RETRO`; does not write `current` to STATE.json
- [ ] `team.flow.yaml` declares `transition_rules` covering BUILDING, REVIEWING, and TESTING states with artifact-based routing
- [ ] `orchestrator.md` FSM loop applies `transition_rules` from the flow config after each sub-agent returns, and is the only entity writing `current` to STATE.json

**Delivered by:** Phases 8a–8c → Conversation 4b

---

### Story 4.1: pathly-setup materializes flow YAMLs and skill files reference the installed path
**As a** user who installed pathly via `pathly-setup --apply`, **I want** the orchestrator to find flow YAML files when I run `/team` from my own project, **so that** pipelines work after install and not just inside the pathly-adapters repo.

**Acceptance Criteria:**
- [ ] After `pathly-setup --apply`, `*.flow.yaml` files exist at the host's agents destination (e.g., `~/.claude/agents/team.flow.yaml`)
- [ ] The installed `team.md`, `debug.md`, and `explore.md` skill files reference the absolute installed path (e.g., `/home/user/.claude/agents/team.flow.yaml`), not `src/pathly_data/core/flows/team.flow.yaml`
- [ ] `pathly-setup --uninstall` removes the materialized flow YAML files
- [ ] `pathly-setup --repair` re-materializes flow YAML files if they are missing

**Delivered by:** Phase 9 → Conversation 5
