# Pathly — Database Schema

---

## One Database

```
~/.pathly/pathly.db          ← the only database. always open.
```

All structured data lives here — global config, runtime state, telemetry, skills, agents.

The selected project folder is **not** a data store.
It is a **workspace** — a directory where agents read and write `.md` files.

```
~/.pathly/pathly.db          ← ALL structured data

C:/my-project/               ← selected project folder (workspace only)
  pathly/
    plans/
      login-flow/
        USER_STORIES.md        ← agent reads this
        IMPLEMENTATION_PLAN.md ← agent reads this
        REVIEW_FAILURES.md     ← reviewer writes → builder reads
        TEST_FAILURES.md       ← tester writes → builder reads
```

---

## How projects are separated

Every runtime table has a `project_root` TEXT column — the absolute path to the
selected project folder. This is how rows from different projects coexist in one DB.

```sql
-- all features in C:/my-project
SELECT * FROM fsm_state WHERE project_root = 'C:/my-project'

-- all features across all projects (for the global dashboard)
SELECT project_root, feature, current FROM fsm_state

-- cost breakdown per project
SELECT project_root, SUM(cost_usd) FROM agent_invocations GROUP BY project_root
```

"Selecting a folder" in the Studio just sets `project_root` in memory.
No DB file is created. No migration runs. The folder only needs to exist
so the server can write `.md` artifact files into it.

---

## Table groups

| Group | Tables | project_root? | Description |
|---|---|---|---|
| **Global config** | 4, 5, 6 | No | Flows, nodes, edges — reusable across all projects |
| **Runtime data** | 1, 2, 3, 7, 8, 9, 10 | Yes — required | FSM state, events, cost, traces — scoped to a project |
| **Scoped config** | 11, 12 | Nullable | Skills + agents — NULL=global, path=local override |

---

## Runtime tables (`project_root` + `feature` required)

### Table 1 — `fsm_events` *(existing — project_root added)*
Append-only log of everything that happened in a feature's pipeline.

| Column | Type | Description |
|---|---|---|
| `seq` | INTEGER PK | Auto-increment |
| `project_root` | TEXT | Absolute path to project folder |
| `feature` | TEXT | Feature name |
| `type` | TEXT | `AGENT_START` · `AGENT_DONE` · `PHASE_START` · `PHASE_DONE` · `STATE_TRANSITION` · `RUNNER_REROUTE` |
| `ts` | TEXT | ISO-8601 |
| `schema_version` | INTEGER | Payload version |
| `payload` | TEXT | Full JSON blob |

Indexes: `(project_root, feature, seq)`, `(project_root, feature, type)`

---

### Table 2 — `fsm_state` *(existing — PK changed to (project_root, feature))*
Current FSM position. One row per feature per project.

| Column | Type | Description |
|---|---|---|
| `project_root` | TEXT PK | Absolute path to project folder |
| `feature` | TEXT PK | Feature name |
| `current` | TEXT | Current stage: `BUILDING` · `REVIEWING` · `DONE` · etc. |
| `rigor` | TEXT | Rigor level for this run |
| `current_conversation` | INTEGER | Which conversation is active |
| `retry_count_by_key` | TEXT | JSON |
| `iteration_by_stage` | TEXT | JSON |
| `updated_at` | TEXT | ISO-8601 |
| `conv_start_sha` | TEXT | Git SHA when conversation started |
| `convs_total` | INTEGER | Total conversations planned |
| `convs_done` | INTEGER | Conversations completed |
| `build_baseline` | TEXT | JSON |
| `extra` | TEXT | JSON extension bag |

---

### Table 3 — `runner_state` *(existing — PK changed to (project_root, feature))*
Live runner execution state.

| Column | Type | Description |
|---|---|---|
| `project_root` | TEXT PK | Absolute path to project folder |
| `feature` | TEXT PK | Feature name |
| `topic` | TEXT | Same as feature (legacy) |
| `flow` | TEXT | `team` · `standard` · `nano` → FK to `flow_definitions.id` |
| `model` | TEXT | Model in use |
| `timeout` | INTEGER | Per-stage timeout (seconds) |
| `run_id` | TEXT | Unique ID for this run |
| `status` | TEXT | `idle` · `running` · `paused` · `done` · `error` · `aborted` |
| `current_state` | TEXT | Current FSM stage |
| `current_adapter` | TEXT | `claude` · `codex` · `copilot` · `antigravity` |
| `iterations` | INTEGER | Total iterations so far |
| `max_iterations` | INTEGER | Limit before auto-abort |
| `cost_usd_so_far` | REAL | Cumulative cost |
| `max_cost_usd` | REAL | Spend cap |
| `autonomy` | TEXT | JSON |
| `pending_menu` | TEXT | JSON |
| `error_kind` | TEXT | Last error type |
| `open_session` | TEXT | JSON |
| `updated_at` | TEXT | ISO-8601 |

---

### Table 7 — `agent_invocations` *(new)*
One row per agent run. Drives monitoring charts, cost breakdown, run history.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `project_root` | TEXT | Project folder path |
| `feature` | TEXT | Feature name |
| `run_id` | TEXT | → `runner_state.run_id` |
| `stage` | TEXT | `BUILD` · `REVIEW` · `TEST` · etc. |
| `conv_id` | TEXT | `bld-01` within the stage |
| `agent_role` | TEXT | `builder` · `reviewer` · `tester` |
| `model` | TEXT | Model used |
| `input_tokens` | INTEGER | |
| `output_tokens` | INTEGER | |
| `tool_uses` | INTEGER | |
| `cost_usd` | REAL | |
| `wall_seconds` | REAL | |
| `result` | TEXT | `PASS` · `FAIL` · `BLOCK` · `ERROR` |
| `summary` | TEXT | AGENT_DONE.summary (full, not truncated) |
| `session_id` | TEXT | |
| `trace_id` | TEXT | → `otel_spans.trace_id` |
| `span_id` | TEXT | → `otel_spans.span_id` |
| `started_at` | TEXT | ISO-8601 |
| `finished_at` | TEXT | ISO-8601 |

---

### Table 8 — `otel_spans` *(new)*
Local OTLP span cache. Written by `otel_export.py` alongside the remote POST.
Trace UI works even with no external collector configured.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `trace_id` | TEXT | 16-byte hex |
| `span_id` | TEXT | 8-byte hex |
| `parent_span_id` | TEXT | null for root spans |
| `project_root` | TEXT | |
| `feature` | TEXT | |
| `name` | TEXT | `invoke_agent builder` |
| `start_time_ns` | INTEGER | Unix epoch nanoseconds |
| `end_time_ns` | INTEGER | |
| `status_code` | TEXT | `OK` · `ERROR` · `UNSET` |
| `status_message` | TEXT | |
| `attributes` | TEXT | JSON flat map of all OTLP attributes |

Unique: `(trace_id, span_id)` — safe to re-import

---

### Table 9 — `skill_overrides` *(new)*
Runtime skill swap — user picks a different skill for a stage before it executes.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `project_root` | TEXT | |
| `feature` | TEXT | |
| `run_id` | TEXT | |
| `stage` | TEXT | Stage to override: `REVIEW` |
| `skill_name` | TEXT | Skill to use: `pathly-review-strict.md` |
| `selected_at` | TEXT | ISO-8601 |
| `status` | TEXT | `pending` · `applied` · `skipped` |

Unique: `(project_root, feature, run_id, stage)`

---

### Table 10 — `stage_artifacts` *(new)*
Mirrors the `.md` files agents write into the DB after each stage.
DB Explorer shows content without opening files.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `project_root` | TEXT | |
| `feature` | TEXT | |
| `run_id` | TEXT | |
| `stage` | TEXT | |
| `artifact_type` | TEXT | `REVIEW_FAILURES` · `TEST_FAILURES` · `USER_STORIES` · `IMPLEMENTATION_PLAN` · `CONVERSATION_PROMPTS` · `RETRO` |
| `content` | TEXT | Full markdown content |
| `file_path` | TEXT | Original path (traceability) |
| `created_at` | TEXT | ISO-8601 |

---

## Global config tables (no `project_root`)

### Table 4 — `flow_definitions`
Flow blueprints. Canvas reads and writes here.

| Column | Type | Description |
|---|---|---|
| `id` | TEXT PK | `team` · `standard` · `nano` · custom slug |
| `name` | TEXT | Human-readable name |
| `description` | TEXT | |
| `rigor` | TEXT | `nano` · `lite` · `standard` · `strict` |
| `version` | INTEGER | Increments on each save |
| `raw_yaml` | TEXT | Original YAML for export / git diff |
| `created_at` | TEXT | ISO-8601 |
| `updated_at` | TEXT | ISO-8601 |

---

### Table 5 — `flow_nodes`
One row per stage in a flow.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `flow_id` | TEXT FK | → `flow_definitions.id` |
| `name` | TEXT | `BUILD` · `REVIEW` · custom |
| `agent_role` | TEXT | `builder` · `reviewer` · `tester` |
| `skill_name` | TEXT | Default skill: `pathly-build.md` |
| `adapter` | TEXT | `claude` · `codex` · `copilot` · `antigravity` |
| `description` | TEXT | |
| `pos_x` | REAL | Canvas position |
| `pos_y` | REAL | Canvas position |

Unique: `(flow_id, name)`

---

### Table 6 — `flow_edges`
Transitions between stages.

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto |
| `flow_id` | TEXT FK | → `flow_definitions.id` |
| `from_node` | TEXT | |
| `to_node` | TEXT | |
| `condition` | TEXT | `PASS` · `FAIL` · `BLOCK` · NULL (unconditional) |
| `label` | TEXT | Display label on canvas edge |

Unique: `(flow_id, from_node, to_node, condition)`

---

## Scoped config tables (`project_root` nullable)

### Table 11 — `skill_definitions`
`project_root = NULL` → global skill, available in every project.
`project_root = path` → local override, only for that project folder.

Lookup pattern — local wins:
```sql
SELECT * FROM skill_definitions
WHERE file_name = 'pathly-review.md'
  AND (project_root = 'C:/my-project' OR project_root IS NULL)
ORDER BY project_root IS NULL   -- 0 (local) sorts before 1 (global)
LIMIT 1
```

| Column | Type | Description |
|---|---|---|
| `id` | TEXT | Slug: `pathly-build` |
| `file_name` | TEXT | `pathly-build.md` |
| `display_name` | TEXT | Shown in UI |
| `category` | TEXT | `build` · `review` · `test` · `plan` · `custom` |
| `content` | TEXT | Full markdown content |
| `description` | TEXT | One-line summary for skill picker |
| `compatible_stages` | TEXT | JSON array: `["BUILD"]` |
| `project_root` | TEXT | NULL = global · path = local |
| `is_custom` | INTEGER | 0 = built-in, 1 = user-created |
| `version` | INTEGER | Increments on each save |
| `created_at` | TEXT | ISO-8601 |
| `updated_at` | TEXT | ISO-8601 |

PK: `(id, COALESCE(project_root, ''))`

---

### Table 12 — `agent_definitions`
`project_root = NULL` → global role.
`project_root = path` → local override (different model or instructions for this project).

| Column | Type | Description |
|---|---|---|
| `role` | TEXT | `builder` · `reviewer` · `tester` · `planner` · `architect` |
| `display_name` | TEXT | Shown in UI |
| `model` | TEXT | `claude-sonnet-4-6` · `claude-opus-4-8` · `claude-haiku-4-5` |
| `description` | TEXT | |
| `instructions` | TEXT | Full system instructions / role contract |
| `capabilities` | TEXT | JSON array |
| `project_root` | TEXT | NULL = global · path = local override |
| `is_custom` | INTEGER | 0 = built-in, 1 = user-created |
| `created_at` | TEXT | ISO-8601 |
| `updated_at` | TEXT | ISO-8601 |

PK: `(role, COALESCE(project_root, ''))`

---

## Table relationships

```
flow_definitions ──< flow_nodes      (1 flow → many nodes)
flow_definitions ──< flow_edges      (1 flow → many edges)

runner_state.flow     ──→ flow_definitions.id
runner_state.run_id   ──→ agent_invocations.run_id
runner_state.run_id   ──→ skill_overrides.run_id
runner_state.run_id   ──→ stage_artifacts.run_id

agent_invocations.trace_id ──→ otel_spans.trace_id
agent_invocations.span_id  ──→ otel_spans.span_id
```

---

## What replaces what

| Old | New | Notes |
|---|---|---|
| `EVENTS.jsonl` | `fsm_events` | already done |
| `STATE.json` | `fsm_state` | already done |
| `team.yaml` | `flow_definitions` + `flow_nodes` + `flow_edges` | new |
| `REVIEW_FAILURES.md` | `stage_artifacts` type=`REVIEW_FAILURES` | file still exists for agents |
| `TEST_FAILURES.md` | `stage_artifacts` type=`TEST_FAILURES` | file still exists for agents |
| one DB per feature folder | rows with `project_root` + `feature` columns | `~/.pathly/pathly.db` holds everything |
