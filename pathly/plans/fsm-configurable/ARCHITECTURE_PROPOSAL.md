# fsm-configurable — Architecture Proposal

## Problem statement

`orchestrator.md` is a generic FSM engine in name but not in practice. It hardcodes:
- State names: BUILDING, REVIEWING, TESTING, RETRO (team-specific)
- Storage path: `plans/<feature>/`
- Routing table: fixed entries for the team pipeline
- Feedback routing: ARCH_FEEDBACK → architect, REVIEW_FAILURES → builder, etc.

`debug.md` and `explore.md` each run their own inline FSM with no STATE.json or EVENTS.jsonl tracking.

Adding a new orchestrated flow today requires editing orchestrator.md. This couples the FSM engine to every flow it needs to support.

---

## Proposed design

### 1. Flow config files (`core/flows/*.flow.yaml`)

Each flow owns a YAML file that fully describes its FSM. The orchestrator is a reader of these files — it has no flow-specific knowledge.

**Required fields:**

| Field | Type | Purpose |
|---|---|---|
| `flow` | string | Human-readable flow name for logging |
| `storage_path` | string | Directory template; `{topic}` is substituted at runtime |
| `states` | list[string] | All valid states for this flow |
| `transitions` | map[string, list[string]] | Valid next-states from each state |
| `agent_map` | map[string, string] | Agent or skill name to invoke per state |
| `feedback_routing` | map[string, string] | Feedback file name → agent to route to |

**Location:** `src/pathly_data/core/flows/` — a new sibling directory of `agents/` and `skills/`.

**Why YAML and not inline in skill files:** The flow config is read by the orchestrator, not by the skill launcher. Keeping it in a separate file means the orchestrator never imports skill logic, and the skill launchers never embed FSM state definitions.

### 2. Orchestrator contract change

The orchestrator receives two new inputs at spawn time:

| Input | Type | Required | Description |
|---|---|---|---|
| `flow_config` | string (path) | yes | Path to the `*.flow.yaml` file for this run |
| `topic` | string | yes | Substituted into `{topic}` in `storage_path`; also used as the feature/symptom/topic name in STATE.json |

Existing inputs (`rigor`, `autoFlow`, `entryStage`) are unchanged.

**Startup sequence the orchestrator must follow:**
1. Verify `flow_config` path exists. If not, stop with HUMAN_QUESTIONS.md.
2. Read and parse the YAML file.
3. Verify required fields (`storage_path`, `states`, `transitions`, `agent_map`, `feedback_routing`) are all present. If any are missing, stop with HUMAN_QUESTIONS.md.
4. Substitute `{topic}` into `storage_path`.
5. Create storage directory if it does not exist.
6. Write initial STATE.json with `state: <first non-DONE state>`.
7. Begin state loop.

### 3. Skill launcher contract

Each skill launcher (team.md, debug.md, explore.md) is responsible only for:
- Parsing the user's invocation inputs
- Spawning the orchestrator with the correct `flow_config` path and `topic`

The skill launcher does not know state names, transitions, or which agents handle which states.

### 4. What does NOT change

- The storage path conventions (plans/, debugs/, explorations/) are preserved — they move into the YAML files rather than being removed.
- STATE.json and EVENTS.jsonl formats are unchanged.
- The feedback file protocol (REVIEW_FAILURES.md, TEST_FAILURES.md, etc.) is unchanged; routing is now config-driven rather than hardcoded.
- The orchestrator's `can_spawn` list in YAML adapters is unchanged (it still needs the same set of agents).

---

## Design decisions

**Why not embed flow config inside the skill launcher file?**
The orchestrator needs to read the config. If the config lives inside the skill file, the orchestrator would need to parse skill file prose, which is fragile. A dedicated YAML file is machine-readable and verifiable with a single grep.

**Why `{topic}` as the placeholder rather than `{feature}` or `{name}`?**
`topic` is the neutral term that works for all three flows: team uses feature names, debug uses symptom names, explore uses exploration topics. A single placeholder name reduces per-flow special-casing in the orchestrator.

**Why core/flows/ and not adapters/?**
Flow configs describe the logical FSM, not host-specific adapter behavior. They should be portable across adapters (claude, codex, copilot) without duplication.

**Why not a JSON schema for flow YAML validation?**
Out of scope for this feature. The orchestrator does runtime validation of required keys (see EC-2 in EDGE_CASES.md). A schema can be added as a follow-on.
