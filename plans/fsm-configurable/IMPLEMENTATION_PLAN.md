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
**Enables:** Phase 5c

---

### Phase 5c — Generalize state.py and eventlog.py   ← Conversation: 3

**File:** `src/pathly_orchestrator/state.py` — MODIFY
**File:** `src/pathly_orchestrator/eventlog.py` — MODIFY

**Why:** `state.py` hardcodes `VALID_STATES` and `TRANSITIONS` for the team pipeline. `eventlog.py` imports and validates against those. After Phase 5b removes the enum from `state.schema.json`, the Python layer would still reject any non-team state name written by a debug or explore flow. Additionally, `_plans_dir()` hardcodes `Path("plans")` — after the `pathly/` consolidation, the CLI command `pathly-state <feature>` will look in the wrong directory.

**Changes to `state.py`:**
1. Remove `STATES`, `VALID_STATES`, and `TRANSITIONS`.
2. Add `load_flow(yaml_path: str) -> dict` — reads and returns a parsed `*.flow.yaml` file.
3. Add `valid_states(flow: dict) -> frozenset[str]` — returns `frozenset(flow.get("states", []))`.
4. Add `flow_transitions(flow: dict) -> dict[str, frozenset[str]]` — returns `{k: frozenset(v) for k, v in flow.get("transitions", {}).items()}`.

**Changes to `eventlog.py`:**
1. Remove the import of `VALID_STATES, TRANSITIONS` from `pathly_orchestrator.state`. Import `valid_states, flow_transitions` instead.
2. Change `write_state(feature: str, state: dict)` → `write_state(storage_path: str, state: dict, flow: dict | None = None)`. When `flow` is provided, validate `current` against `valid_states(flow)` and validate the transition against `flow_transitions(flow)`. When `flow` is `None`, skip validation entirely (graceful degradation for direct LLM writes).
3. Change `append_event(feature: str, event: dict)` → `append_event(storage_path: str, event: dict, flow: dict | None = None)`. Same optional guard: only validate `STATE_TRANSITION.to` when `flow` is provided.
4. Replace the hardcoded `_plans_dir() → Path("plans")` and `_feature_dir(feature)` helpers with a single `_resolve_path(storage_path: str) -> Path` that treats the argument as a full directory path.
5. Update `_state_path` and `_events_path` to call `_resolve_path(storage_path)`.
6. Update `_state_cli()` so `pathly-state` accepts a full storage path (e.g. `pathly/plans/auth-rewrite`) rather than a bare feature name. Update `_cli()` the same way for `pathly-events summary`.

**CLI backward compatibility decision (closed — do not re-open):** Use the backward-compatible alias approach. `pathly-state <feature>` (bare name, no `/`) auto-prepends `pathly/plans/` before resolving. `pathly-state pathly/plans/<feature>` (full path, contains `/`) is used as-is. This gives zero user action required and zero breakage. Record the decision as a comment in `eventlog.py` above `_state_cli`: `# bare feature names auto-resolved to pathly/plans/<name>/ for backward compat`.

**Add `pathly-validate-flow` CLI (new deliverable, same conversation):** After implementing points 1–6, add a `pathly-validate-flow <path>` entry point in `pyproject.toml` backed by a `validate_flow_cli()` function in `state.py`. The function: loads the YAML at the given path, checks all five required fields are present, prints each missing field with a clear error message, exits 0 on success and 1 on failure. This lets users verify a flow YAML before running it. Implementation is ~15 lines. Register the entry point as `pathly-validate-flow = pathly_orchestrator.state:validate_flow_cli`.

**Done when:**
- `grep "VALID_STATES\|TRANSITIONS" src/pathly_orchestrator/state.py` returns no output.
- `grep "load_flow\|valid_states\|flow_transitions" src/pathly_orchestrator/state.py` returns all three function definitions.
- `grep "Path(\"plans\")" src/pathly_orchestrator/eventlog.py` returns no output.
- `grep "flow: dict" src/pathly_orchestrator/eventlog.py` returns both `write_state` and `append_event` signatures.

**Delivers stories:** S2.3
**Depends on:** Phase 5b complete (same conversation, final step)
**Enables:** Conv 4

---

### Phase 6 — Update team.md to pass flow_config   ← Conversation: 4

**File:** `src/pathly_data/core/skills/team.md` — MODIFY

In the `## Spawn orchestrator` section (added by agent-architecture-refactor Conv 4), add `flow_config: src/pathly_data/core/flows/team.flow.yaml` to the spawn parameters. Remove any hardcoded team state names from the spawn block if present.

**Done when:**
- `grep "flow_config" src/pathly_data/core/skills/team.md` returns a line with `src/pathly_data/core/flows/team.flow.yaml`.
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
  flow_config: src/pathly_data/core/flows/debug.flow.yaml
  topic: <symptom-name>
  rigor: <rigor>
  autoFlow: <autoFlow>
```

**Done when:**
- `grep "orchestrator" src/pathly_data/core/skills/debug.md` returns the spawn instruction.
- `grep "flow_config" src/pathly_data/core/skills/debug.md` returns `src/pathly_data/core/flows/debug.flow.yaml`.
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
  flow_config: src/pathly_data/core/flows/explore.flow.yaml
  topic: <topic>
  rigor: <rigor>
  autoFlow: <autoFlow>
```

**Done when:**
- `grep "orchestrator" src/pathly_data/core/skills/explore.md` returns the spawn instruction.
- `grep "flow_config" src/pathly_data/core/skills/explore.md` returns `src/pathly_data/core/flows/explore.flow.yaml`.
- `grep -i "FRAMING\|ANALYZING\|TRACING\|CONCLUDING" src/pathly_data/core/skills/explore.md` returns no inline step logic.

**Delivers stories:** S3.3
**Depends on:** Phase 3 (explore.flow.yaml exists); Phase 4 (orchestrator is generic)
**Enables:** nothing (final phase)

---

### Phase 8a — Extend team.flow.yaml with transition_rules   ← Conversation: 4b

**File:** `src/pathly_data/core/flows/team.flow.yaml` — MODIFY

Add a `transition_rules` top-level key. Each entry maps a state name to an ordered list of artifact checks and a default next state. Orchestrator evaluates checks top-to-bottom; first match wins; `default` fires when no artifact is present.

```yaml
transition_rules:
  BUILDING:
    on_artifact:
      BLOCKED_ON_HUMAN.md: BLOCKED_ON_HUMAN
    default: REVIEWING
  REVIEWING:
    on_artifact:
      REVIEW_FAILURES.md: BUILDING
      MORE_CONVS_NEEDED.md: BUILDING
    default: TESTING
  TESTING:
    on_artifact:
      TEST_FAILURES.md: TESTING
      BLOCKED_ON_HUMAN.md: BLOCKED_ON_HUMAN
    default: RETRO
```

Artifact paths are resolved relative to the run's `storage_path` (e.g. `pathly/plans/auth-rewrite/REVIEW_FAILURES.md`).

**Done when:**
- `grep "transition_rules" src/pathly_data/core/flows/team.flow.yaml` returns the new section.
- `grep "MORE_CONVS_NEEDED" src/pathly_data/core/flows/team.flow.yaml` returns a match.

**Delivers stories:** S3.4 (partial)
**Depends on:** Phase 1 complete (team.flow.yaml exists); Conv 4 DONE (base structure confirmed)
**Enables:** Phase 8b

---

### Phase 8b — Strip STATE.json transition writes from team sub-skills   ← Conversation: 4b

**Files:**
- `src/pathly_data/core/skills/team/build.md` — MODIFY
- `src/pathly_data/core/skills/team/review.md` — MODIFY
- `src/pathly_data/core/skills/team/test.md` — MODIFY

**Changes to `team/build.md`:**
1. Remove the "Transition state → REVIEWING" line at the end.
2. Remove the "Transition state to X: Write STATE.json" instruction from the preamble — build.md no longer transitions state.
3. Add a closing line: "Return. Orchestrator determines next state from transition_rules."

**Changes to `team/review.md`:**
1. Remove the routing block:
   ```
   If more TODO conversations remain: transition state → BUILDING.
   Else: transition state → TESTING.
   ```
2. Replace with: if more TODO conversations remain, write `MORE_CONVS_NEEDED.md` under the run's storage path. Write no file if all conversations are done.
3. Remove the "Transition state to X: Write STATE.json" preamble instruction.
4. **Keep:** the PROGRESS.md update (marking Conv N as DONE) — this is reporting, not routing.
5. Add a closing line: "Return. Orchestrator determines next state from transition_rules."

**Changes to `team/test.md`:**
1. Remove the "Transition state → RETRO" line at the end.
2. Remove the "Transition state to X: Write STATE.json" preamble instruction.
3. Keep the internal fix loop intact — tester writes TEST_FAILURES.md and loops with builder internally. Only the final transition out of TESTING is removed.
4. Add a closing line: "Return. Orchestrator determines next state from transition_rules."

**Done when:**
- `grep "Transition state" src/pathly_data/core/skills/team/build.md` returns no output.
- `grep "Transition state" src/pathly_data/core/skills/team/review.md` returns no output.
- `grep "Transition state" src/pathly_data/core/skills/team/test.md` returns no output.
- `grep "→ REVIEWING\|→ TESTING\|→ RETRO\|→ BUILDING" src/pathly_data/core/skills/team/build.md src/pathly_data/core/skills/team/review.md src/pathly_data/core/skills/team/test.md` returns no output (state names removed from routing context; may appear in prose description only).
- `grep "MORE_CONVS_NEEDED" src/pathly_data/core/skills/team/review.md` returns the new write instruction.

**Delivers stories:** S3.4 (partial)
**Depends on:** Phase 8a complete (transition_rules exist in team.flow.yaml before sub-skills reference them)
**Enables:** Phase 8c

---

### Phase 8c — Update orchestrator.md FSM loop to apply transition_rules   ← Conversation: 4b

**File:** `src/pathly_data/core/agents/orchestrator.md` — MODIFY

After each sub-agent or sub-skill returns, the orchestrator currently relies on the sub-skill having written the next state into STATE.json. Replace this with a generic transition_rules evaluation loop.

**Changes:**
1. After spawning a sub-agent/skill and receiving control back, read `transition_rules[current_state]` from the loaded flow config.
2. For each entry in `on_artifact` (in order): check whether that file exists under the run's storage_path. First match → set next_state to the mapped state value.
3. If no artifact matched → set next_state to `default`.
4. Write STATE.json with `{"current": next_state}`. Append STATE_TRANSITION event to EVENTS.jsonl.
5. Continue FSM loop with next_state.
6. If current_state has no `transition_rules` entry in the flow config, proceed to `default` state from the `transitions` map (graceful — flows without transition_rules still work).

**Done when:**
- `grep "transition_rules" src/pathly_data/core/agents/orchestrator.md` returns the evaluation logic.
- `grep "on_artifact" src/pathly_data/core/agents/orchestrator.md` returns the artifact check loop.
- Orchestrator.md contains a note: "Orchestrator is the only entity that writes `current` to STATE.json. Sub-skills write artifacts only."

**Delivers stories:** S3.4 (complete)
**Depends on:** Phase 8b complete; Phase 4 complete (orchestrator is already generic, reads flow_config)
**Enables:** Conv 5 (materialize)

---

### Phase 9 — Materialize flow YAMLs during pathly-setup   ← Conversation: 5

**Files:**
- `src/install_cli/resources.py` — MODIFY: add `core_flows_path()` helper
- `src/install_cli/stitch.py` — MODIFY: add `flows_dest` parameter to `stitch_skill()`
- `src/install_cli/materialize.py` — MODIFY: add `materialize_flows()` function
- `src/install_cli/setup_command.py` — MODIFY: call `materialize_flows`; pass `flows_dest=dest` to `stitch_skill`

**Why:** Flow YAML files live in the package at `src/pathly_data/core/flows/`. After install, the user's project has no `src/pathly_data/` directory — the orchestrator agent cannot Read `src/pathly_data/core/flows/team.flow.yaml`. Fix: copy flow YAMLs to the host's agents destination (e.g., `~/.claude/agents/`) during `pathly-setup`, and replace the `src/pathly_data/core/flows/` prefix in stitched skill content with the absolute installed path.

**Changes to `resources.py`:**
Add `core_flows_path()` after the existing `core_templates_path()` function:
```python
def core_flows_path() -> Path:
    return _root() / "core" / "flows"
```

**Changes to `stitch.py`:**
Add a `flows_dest: Path | None = None` keyword parameter to `stitch_skill()`. After the existing `variables` substitution loop, add:
```python
if flows_dest is not None:
    body = body.replace("src/pathly_data/core/flows/", flows_dest.as_posix() + "/")
```
This converts `flow_config: src/pathly_data/core/flows/team.flow.yaml` → `flow_config: /home/user/.claude/agents/team.flow.yaml` in the stitched skill output. Use `.as_posix()` so forward slashes are used in the skill text regardless of OS.

**Changes to `materialize.py`:**
Add after the existing `materialize()` function:
```python
def materialize_flows(
    src_flows: Path,
    dest: Path,
    *,
    repair: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> list[str]:
    """Copy *.flow.yaml files from src_flows to dest. Returns list of filenames written."""
    files = {f.name: f.read_text(encoding="utf-8") for f in src_flows.glob("*.flow.yaml")}
    _validate_flows(files)
    return materialize(files, dest, repair=repair, force=force, dry_run=dry_run)

_REQUIRED_FLOW_KEYS = {"storage_path", "states", "transitions", "agent_map", "feedback_routing"}

def _validate_flows(files: dict[str, str]) -> None:
    """Raise ValueError listing all missing keys for any malformed flow YAML."""
    import yaml
    errors: list[str] = []
    for name, text in files.items():
        parsed = yaml.safe_load(text) or {}
        missing = _REQUIRED_FLOW_KEYS - parsed.keys()
        if missing:
            errors.append(f"{name}: missing required keys: {sorted(missing)}")
    if errors:
        raise ValueError("Flow YAML validation failed:\n" + "\n".join(errors))
```
Flow files are tracked in the same manifest as agents, so `uninstall()` removes them automatically — no extra uninstall logic needed.

> **CRITICAL:** Phase 9 is the last phase and the easiest to skip. Without it, the installed system is completely broken — orchestrator.md cannot Read `src/pathly_data/core/flows/` paths from a user's project. Conv 5 must run; it is not optional cleanup.

**Changes to `setup_command.py`:**
1. Add `core_flows_path` to the import from `.resources`.
2. Add `materialize_flows` to the import from `.materialize`.
3. In `_run_host()`, after computing `dest` and before agent stitching, call:
   ```python
   materialize_flows(core_flows_path(), dest, repair=repair, force=force, dry_run=dry_run)
   ```
4. In the skill stitching loop, change `stitch_skill(core_file, meta_file)` to `stitch_skill(core_file, meta_file, flows_dest=dest)`.

**Done when:**
- `grep "core_flows_path" src/install_cli/resources.py` returns the function definition.
- `grep "flows_dest" src/install_cli/stitch.py` returns the parameter in `stitch_skill`.
- `grep "materialize_flows" src/install_cli/materialize.py` returns the function definition.
- `grep "materialize_flows" src/install_cli/setup_command.py` returns both the import line and the call line.
- `grep "flows_dest=dest" src/install_cli/setup_command.py` returns the updated `stitch_skill` call.

**Delivers stories:** S4.1
**Depends on:** Conv 4 DONE (flow YAMLs exist at `src/pathly_data/core/flows/`); Phase 5c DONE (flow-agnostic Python layer)
**Enables:** end users can run pathly after `pathly-setup --apply`

---

## Key Decisions

- **pathly/ root:** All runtime output lives under `pathly/` — `pathly/plans/`, `pathly/debugs/`, `pathly/explorations/`, `pathly/pipeline-walkthrough/`. The `storage_path` field in each flow YAML is the single source of truth for where output lands.
- Flow YAML files live under `core/flows/` — alongside agents/ and skills/ — because they are runtime artifacts, not adapter-specific config.
- Storage paths use a `{topic}` placeholder substituted at runtime; flow-type prefixes (pathly/plans/, pathly/debugs/, pathly/explorations/) are defined in the YAML, not hardcoded in orchestrator.md.
- Conv 1 (pathly/ path fixes) and Conv 2 (YAML creation) are safe to run before agent-architecture-refactor Conv 4. Conv 3 and Conv 4 are blocked on that dependency.
- Criteria specify WHAT content the files must contain, not HOW they are formatted (per CANDIDATE-001).
- Each criterion is independently falsifiable with a single grep (per CANDIDATE-002).
- **Flow config paths use `src/pathly_data/core/flows/` prefix** — all `flow_config:` values in skill files reference the repo-relative path so agents running from the repo root can Read them. This works in the development/repo context only.
- **Install gap — handled by Phase 9 / Conv 5:** Flow YAML files at `src/pathly_data/core/flows/` are not accessible from a user's project. Phase 9 closes this by materializing flow YAMLs to the host's agents destination (e.g., `~/.claude/agents/`) and rewriting the `src/pathly_data/core/flows/` prefix in stitched skill files to the absolute installed path. Conv 5 must run after Conv 4 so the flow YAMLs exist before they are materialized.
