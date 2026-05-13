# fsm-configurable — Implementation Plan

## Overview

Extract all flow-specific FSM configuration out of orchestrator.md (and out of inline skill logic in debug.md and explore.md) into `core/flows/*.flow.yaml` files. Rewrite orchestrator.md as a generic FSM engine that reads its state machine, agent_map, storage_path, and feedback_routing entirely from the flow config it receives at spawn time. Update team.md, debug.md, and explore.md to spawn the orchestrator with the appropriate flow config path.

Additionally, consolidate all runtime output directories under a `pathly/` root so the project root stays clean: `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/`, `pathly/pipeline-walkthrough/`.

## Dependency

**Blocked on:** `agent-architecture-refactor` Conv 4 must be DONE before Conv 3 and Conv 4 of this feature begin.
- Conv 4 converts `team.md` to a thin launcher and enriches `orchestrator.md` with FSM sections from `team.md`.
- This feature then generalizes that orchestrator to accept any flow config.
- Conv 1 (pathly/ consolidation) and Conv 2 (creating flow YAML files) are safe to run before agent-architecture-refactor Conv 4 completes.

## Pre-flight

Before starting Conv 1: run `git status` to confirm a clean working tree.
Before starting Conv 3: confirm `agent-architecture-refactor` Conv 4 is DONE in `plans/agent-architecture-refactor/PROGRESS.md`.

---

## Phases

### Phase 0a — Update team.md feature detection scan path   ← Conversation: 1

**File:** `src/pathly_data/core/skills/team.md` — MODIFY

In the `## Feature detection` section, update the scan path for STATE.json files:

Replace:
```
Read `plans/*/STATE.json` files, sorted by modification time (newest first).
```
With:
```
Read `pathly/plans/*/STATE.json` files, sorted by modification time (newest first).
```

Also update any other references to `plans/*/` in the feature detection block to use `pathly/plans/*/`.

**Done when:** `grep "pathly/plans" src/pathly_data/core/skills/team.md` returns at least one match in the feature detection section.
**Delivers stories:** S0.1 (partial)
**Depends on:** nothing
**Enables:** Phase 0b; consistent with Conv 2 flow YAML storage_paths

---

### Phase 0b — Update orchestrator.md artifact archiving path   ← Conversation: 1

**File:** `src/pathly_data/core/agents/orchestrator.md` — MODIFY

In the `## Artifact archiving` section (sourced from team.md), update the archive destination from `pipeline-walkthrough/<feature>/artifacts/` to `pathly/pipeline-walkthrough/<feature>/artifacts/`.

Also update any `plans/<feature>/feedback/` references to `pathly/plans/<feature>/feedback/` in the artifact archiving rule.

**Done when:** `grep "pathly/pipeline-walkthrough" src/pathly_data/core/agents/orchestrator.md` returns a match.
**Delivers stories:** S0.1 (complete)
**Depends on:** Phase 0a (same conversation, prior phase)
**Enables:** Conv 2 (flow YAMLs use pathly/ prefix from the start)

---

### Phase 1 — Create team.flow.yaml   ← Conversation: 2

**File:** `src/pathly_data/core/flows/team.flow.yaml` — CREATE

Define the full team pipeline FSM in YAML. Fields required:

```yaml
flow: team
storage_path: "pathly/plans/{topic}/"
states:
  - IDLE
  - STORMING
  - PLANNING
  - BUILDING
  - REVIEWING
  - TESTING
  - RETRO
  - BLOCKED_ON_HUMAN
  - DONE
transitions:
  # full valid transition map
agent_map:
  STORMING: team/discover
  PLANNING: team/plan
  BUILDING: team/build
  REVIEWING: team/review
  TESTING: team/test
  RETRO: team/retro
  BLOCKED_ON_HUMAN: wait
feedback_routing:
  ARCH_FEEDBACK: architect
  REVIEW_FAILURES: builder
  TEST_FAILURES: builder
  IMPL_QUESTIONS: planner
  DESIGN_QUESTIONS: architect
  HUMAN_QUESTIONS: human
```

**Done when:** `src/pathly_data/core/flows/team.flow.yaml` exists and contains `storage_path`, `states`, `transitions`, `agent_map`, and `feedback_routing` keys.
**Delivers stories:** S1.1
**Depends on:** nothing
**Enables:** Phase 4 (orchestrator generalization reads this file as its reference)

---

### Phase 2 — Create debug.flow.yaml   ← Conversation: 2

**File:** `src/pathly_data/core/flows/debug.flow.yaml` — CREATE

Define the debug FSM in YAML. States must match the implicit FSM already described in debug.md comments. Fields required:

```yaml
flow: debug
storage_path: "pathly/debugs/{topic}/"
states:
  - INVESTIGATING
  - REPRODUCING
  - ROOT_CAUSE_FOUND
  - FIXING
  - VERIFYING
  - DONE
transitions:
  # full valid transition map
agent_map:
  INVESTIGATING: scout
  REPRODUCING: builder
  ROOT_CAUSE_FOUND: builder
  FIXING: builder
  VERIFYING: tester
feedback_routing:
  TEST_FAILURES: builder
  HUMAN_QUESTIONS: human
```

**Done when:** `src/pathly_data/core/flows/debug.flow.yaml` exists and contains `storage_path`, `states`, `transitions`, `agent_map`, and `feedback_routing` keys.
**Delivers stories:** S1.2
**Depends on:** nothing
**Enables:** Phase 7 (debug.md spawn update)

---

### Phase 3 — Create explore.flow.yaml   ← Conversation: 2

**File:** `src/pathly_data/core/flows/explore.flow.yaml` — CREATE

Define the explore FSM in YAML. States derived from the implicit flow in explore.md. Fields required:

```yaml
flow: explore
storage_path: "pathly/explorations/{topic}/"
states:
  - FRAMING
  - ANALYZING
  - TRACING
  - CONCLUDING
  - DONE
transitions:
  # full valid transition map
agent_map:
  FRAMING: explorer
  ANALYZING: explorer
  TRACING: explorer
  CONCLUDING: explorer
feedback_routing:
  HUMAN_QUESTIONS: human
```

**Done when:** `src/pathly_data/core/flows/explore.flow.yaml` exists and contains `storage_path`, `states`, `transitions`, `agent_map`, and `feedback_routing` keys.
**Delivers stories:** S1.3
**Depends on:** nothing
**Enables:** Phase 8 (explore.md spawn update)

---

### Phase 4 — Generalize orchestrator.md   ← Conversation: 3

**File:** `src/pathly_data/core/agents/orchestrator.md` — MODIFY

**Pre-condition:** `agent-architecture-refactor` Conv 4 is DONE (orchestrator.md already has FSM sections from team.md).

Replace all hardcoded team-specific content with flow-config-driven equivalents:

1. **Inputs block:** add `flow_config` (path to a `*.flow.yaml` file) and `topic` alongside the existing FEATURE/rigor/autoFlow/entryStage inputs.
2. **Startup:** read and parse `flow_config` at the start of each run. All subsequent behavior derives from the parsed config.
3. **storage_path:** replace hardcoded `pathly/plans/<feature>/` with the `storage_path` field from the config (substituting `{topic}` with the received topic value).
4. **State list and transitions:** replace hardcoded state names with the `states` and `transitions` from the config.
5. **agent_map / routing table:** replace the hardcoded team pipeline routing table with a loop over `agent_map` from the config.
6. **feedback_routing:** replace hardcoded ARCH_FEEDBACK → architect etc. entries with the `feedback_routing` map from the config.
7. **No team-specific state names** (BUILDING, REVIEWING, TESTING, RETRO) should remain as literals outside of comments.

**Done when:**
- `grep -i "BUILDING\|REVIEWING\|TESTING\|RETRO" src/pathly_data/core/agents/orchestrator.md` returns only comment lines (lines starting with `#` or `>`), not logic lines.
- `grep "flow_config" src/pathly_data/core/agents/orchestrator.md` returns the inputs declaration and the startup read instruction.
- `grep "storage_path" src/pathly_data/core/agents/orchestrator.md` returns a line referencing the config-derived value, not a hardcoded `plans/` or `pathly/plans/` string.

**Delivers stories:** S2.1
**Depends on:** agent-architecture-refactor Conv 4 DONE; Phase 0b (pathly/ prefix already in place); Phases 1–3 complete (YAML files exist as reference)
**Enables:** Phase 5, then Conv 4

---

### Phase 5 — Update orchestrator.yaml (both adapters)   ← Conversation: 3

**File:** `src/pathly_data/adapters/claude/_meta/orchestrator.yaml` — MODIFY
**File:** `src/pathly_data/adapters/codex/_meta/orchestrator.yaml` — MODIFY (if file exists; skip with a note if not)

Add `flow_config` as a declared input parameter. The existing `model`, `tools`, and `can_spawn` fields remain unchanged.

Example addition:
```yaml
inputs:
  flow_config:
    description: "Path to a *.flow.yaml file defining the FSM for this run"
    required: true
  topic:
    description: "Feature name, symptom name, or exploration topic — substituted into storage_path"
    required: true
```

**Done when:**
- `grep "flow_config" src/pathly_data/adapters/claude/_meta/orchestrator.yaml` returns the new field.
- If codex adapter exists: same grep returns the new field.

**Delivers stories:** S2.2
**Depends on:** Phase 4 complete
**Enables:** Phase 5b

---

### Phase 5b — Update state.schema.json to allow any state string   ← Conversation: 3

**File:** `schemas/state.schema.json` — MODIFY

The schema currently validates `STATE.json` with a hardcoded `enum` of team pipeline states and a hardcoded `transitions` block at the bottom. Both must go now that the FSM is generic.

Two changes:
1. Replace the `current` field's `enum` array with `"type": "string", "minLength": 1`.
2. Remove the `transitions` block at the bottom of the file — it is team-pipeline-specific and has no place in a generic schema.

All other fields (`feature`, `rigor`, `current_conversation`, `updated_at`, etc.) stay unchanged.

**Done when:**
- `grep "BUILDING\|REVIEWING\|RETRO" schemas/state.schema.json` returns no output.
- `grep "\"type\": \"string\"" schemas/state.schema.json` matches the `current` property line.
- `grep "\"transitions\"" schemas/state.schema.json` returns no output.

**Delivers stories:** S2.1 (complete — STATE.json schema now matches generic FSM output)
**Depends on:** Phase 5 complete (same conversation, natural final step)
**Enables:** Conv 4

---

### Phase 6 — Update team.md to pass flow_config   ← Conversation: 4

**File:** `src/pathly_data/core/skills/team.md` — MODIFY

In the `## Spawn orchestrator` section (added by agent-architecture-refactor Conv 4), add `flow_config: core/flows/team.flow.yaml` to the spawn parameters. Remove any hardcoded team state names from the spawn block if present.

**Done when:**
- `grep "flow_config" src/pathly_data/core/skills/team.md` returns a line with `core/flows/team.flow.yaml`.
- `grep -i "BUILDING\|REVIEWING\|TESTING\|RETRO" src/pathly_data/core/skills/team.md` returns no results in the orchestrator spawn block.

**Delivers stories:** S3.1
**Depends on:** Phase 4 and Phase 5 complete; agent-architecture-refactor Conv 4 DONE
**Enables:** Phase 7

---

### Phase 7 — Rewrite debug.md to spawn orchestrator   ← Conversation: 4

**File:** `src/pathly_data/core/skills/debug.md` — MODIFY

Replace the inline FSM logic (the six explicit steps mapping to INVESTIGATING → REPRODUCING → ROOT_CAUSE_FOUND → FIXING → VERIFYING → DONE) with a `## Spawn orchestrator` section that delegates to the orchestrator agent.

**Keep:** argument parsing, symptom-name detection, any pre-spawn setup.
**Remove:** inline agent spawning for each debug step, inline state-transition comments, any inline feedback file protocol that duplicates the orchestrator's protocol.
**Add:**
```
Spawn **orchestrator** agent:
  flow_config: core/flows/debug.flow.yaml
  topic: <symptom-name>
  rigor: <rigor>
  autoFlow: <autoFlow>
```

**Done when:**
- `grep "orchestrator" src/pathly_data/core/skills/debug.md` returns the spawn instruction.
- `grep "flow_config" src/pathly_data/core/skills/debug.md` returns `core/flows/debug.flow.yaml`.
- `grep -i "INVESTIGATING\|ROOT_CAUSE_FOUND\|FIXING\|VERIFYING" src/pathly_data/core/skills/debug.md` returns no inline step logic.

**Delivers stories:** S3.2
**Depends on:** Phase 2 (debug.flow.yaml exists); Phase 4 (orchestrator is generic)
**Enables:** Phase 8

---

### Phase 8 — Rewrite explore.md to spawn orchestrator   ← Conversation: 4

**File:** `src/pathly_data/core/skills/explore.md` — MODIFY

Replace the inline three-phase explorer spawning logic with a `## Spawn orchestrator` section.

**Keep:** argument parsing, topic detection.
**Remove:** inline three-phase explorer spawning, inline state-transition logic, any implicit FSM references.
**Add:**
```
Spawn **orchestrator** agent:
  flow_config: core/flows/explore.flow.yaml
  topic: <topic>
  rigor: <rigor>
  autoFlow: <autoFlow>
```

**Done when:**
- `grep "orchestrator" src/pathly_data/core/skills/explore.md` returns the spawn instruction.
- `grep "flow_config" src/pathly_data/core/skills/explore.md` returns `core/flows/explore.flow.yaml`.
- `grep -i "FRAMING\|ANALYZING\|TRACING\|CONCLUDING" src/pathly_data/core/skills/explore.md` returns no inline step logic.

**Delivers stories:** S3.3
**Depends on:** Phase 3 (explore.flow.yaml exists); Phase 4 (orchestrator is generic)
**Enables:** nothing (final phase)

---

## Key Decisions

- **pathly/ root:** All runtime output lives under `pathly/` — `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/`, `pathly/pipeline-walkthrough/`. The `storage_path` field in each flow YAML is the single source of truth for where output lands.
- Flow YAML files live under `core/flows/` — alongside agents/ and skills/ — because they are runtime artifacts, not adapter-specific config.
- Storage paths use a `{topic}` placeholder substituted at runtime; flow-type prefixes (pathly/plans/, pathly/debugs/, pathly/explorations/) are defined in the YAML, not hardcoded in orchestrator.md.
- Conv 1 (pathly/ path fixes) and Conv 2 (YAML creation) are safe to run before agent-architecture-refactor Conv 4. Conv 3 and Conv 4 are blocked on that dependency.
- Criteria specify WHAT content the files must contain, not HOW they are formatted (per CANDIDATE-001).
- Each criterion is independently falsifiable with a single grep (per CANDIDATE-002).
