# USER_STORIES.md — studio-backend

## Story Map

| Story | Title | Conv |
|---|---|---|
| S1.1 | Centralized DB | Conv 1 |
| S1.2 | Updated helpers | Conv 1 |
| S1.3 | Seed data | Conv 2 |
| S2.1 | Callers updated | Conv 2 |
| S3.1 | Services layer | Conv 3 |
| S4.1 | Feature/flow/skills/agents/traces endpoints | Conv 4 |
| S4.2 | Override + project endpoints | Conv 4 |

---

## S1.1 — Centralized DB

**As a** Studio developer,
**I want** `get_db()` to take no arguments and return a connection to `~/.pathly/pathly.db`,
**So that** all pipeline runs and Studio queries share one database and cross-feature queries are possible.

### Acceptance Criteria

- AC1.1.1: `get_db()` called with no arguments does not raise an error.
- AC1.1.2: The returned connection targets `~/.pathly/pathly.db` (resolved via `Path.home()`).
- AC1.1.3: The directory `~/.pathly/` is created automatically if it does not exist.
- AC1.1.4: The DB contains a `schema_version` table after first call.
- AC1.1.5: All 12 tables exist: `fsm_events`, `fsm_state`, `runner_state`, `flow_definitions`, `flow_nodes`, `flow_edges`, `agent_invocations`, `otel_spans`, `skill_overrides`, `stage_artifacts`, `skill_definitions`, `agent_definitions`.
- AC1.1.6: Calling `get_db()` twice from the same process does not create duplicate tables (migration is idempotent).
- AC1.1.7: WAL mode is enabled (`PRAGMA journal_mode=WAL` confirmed after connection).

**Verify:**
```bash
python -c "
from pathly_orchestrator.db import get_db
conn = get_db()
tables = [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()]
assert len(tables) >= 12, f'Expected 12 tables, got: {tables}'
assert conn.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
print('OK:', sorted(tables))
"
```

---

## S1.2 — Updated helpers

**As a** backend developer,
**I want** all 8 existing DB helpers updated to accept `project_root` as a parameter and 10 new helpers added for the new tables,
**So that** every DB operation carries the correct isolation key and the services layer has a full SQL API to call.

### Existing helpers (updated signatures)

| Helper | New signature |
|---|---|
| `append_event` | `append_event(conn, project_root, feature, event_dict)` |
| `read_events` | `read_events(conn, project_root, feature, since_seq=0)` |
| `read_last_agent_done` | `read_last_agent_done(conn, project_root, feature)` |
| `write_state` | `write_state(conn, project_root, feature, state_dict)` |
| `read_state` | `read_state(conn, project_root, feature)` |
| `write_runner_state` | `write_runner_state(conn, project_root, feature, runner_dict)` |
| `read_runner_state` | `read_runner_state(conn, project_root, feature)` |
| `mark_stale_runners` | `mark_stale_runners(conn)` (no project_root — global sweep) |

### New helpers (tables 7–12)

| Helper | Table | Purpose |
|---|---|---|
| `upsert_flow_definition` | `flow_definitions` | Insert or replace a flow |
| `read_flow_definitions` | `flow_definitions` | List all flows, optional project_root filter |
| `upsert_skill_definition` | `skill_definitions` | Insert or replace a skill |
| `read_skill_definitions` | `skill_definitions` | List skills, optional project_root filter |
| `upsert_agent_definition` | `agent_definitions` | Insert or replace an agent |
| `read_agent_definitions` | `agent_definitions` | List agents, optional project_root filter |
| `write_agent_invocation` | `agent_invocations` | Record a single agent invocation |
| `read_agent_invocations` | `agent_invocations` | List invocations for a feature |
| `write_skill_override` | `skill_overrides` | Write a per-run skill override |
| `read_skill_override` | `skill_overrides` | Read active override for a stage |

### Acceptance Criteria

- AC1.2.1: Every existing helper passes `project_root` through to its WHERE clause or INSERT.
- AC1.2.2: `read_events(conn, project_root, feature, since_seq=0)` returns only rows matching `project_root` and `feature`.
- AC1.2.3: `append_event(conn, project_root, feature, event_dict)` inserts a row with the correct `project_root` value.
- AC1.2.4: All 10 new helpers exist and are importable from `pathly_orchestrator.db`.
- AC1.2.5: `upsert_flow_definition` is idempotent — calling it twice with same data produces one row.
- AC1.2.6: `read_skill_definitions` with `project_root=None` returns only global (NULL project_root) rows.
- AC1.2.7: `read_skill_override` returns `None` when no row matches.

**Verify:**
```bash
python -c "
from pathly_orchestrator.db import (
    get_db, append_event, read_events, read_last_agent_done,
    write_state, read_state, write_runner_state, read_runner_state,
    mark_stale_runners, upsert_flow_definition, read_flow_definitions,
    upsert_skill_definition, read_skill_definitions, upsert_agent_definition,
    read_agent_definitions, write_agent_invocation, read_agent_invocations,
    write_skill_override, read_skill_override
)
print('All helpers importable: OK')
"
```

---

## S1.3 — Seed data

**As a** developer starting Pathly for the first time,
**I want** the DB to be pre-populated with flows, skills, and agents from `src/pathly_data/`,
**So that** Studio can show the catalog without requiring a separate import step.

### Acceptance Criteria

- AC1.3.1: After calling `get_db()` on a fresh DB, `flow_definitions` has at least 1 row.
- AC1.3.2: After calling `get_db()` on a fresh DB, `skill_definitions` has at least 1 row.
- AC1.3.3: After calling `get_db()` on a fresh DB, `agent_definitions` has at least 1 row.
- AC1.3.4: Calling `get_db()` twice produces the same row counts (INSERT OR IGNORE is used).
- AC1.3.5: If a `*.flow.yaml` file is missing or malformed, `get_db()` logs a warning and continues without raising an exception.
- AC1.3.6: If the `src/pathly_data/` directory is not found, seed is skipped silently (no crash).
- AC1.3.7: Seed rows have `project_root = NULL` (they are global catalog entries).

**Verify:**
```bash
python -c "
from pathly_orchestrator.db import get_db
import os, pathlib
# delete to force fresh seed
db_path = pathlib.Path.home() / '.pathly' / 'pathly.db'
if db_path.exists():
    os.remove(db_path)
conn = get_db()
flows = conn.execute('SELECT COUNT(*) FROM flow_definitions').fetchone()[0]
skills = conn.execute('SELECT COUNT(*) FROM skill_definitions').fetchone()[0]
agents = conn.execute('SELECT COUNT(*) FROM agent_definitions').fetchone()[0]
assert flows > 0, f'No flows seeded'
assert skills > 0, f'No skills seeded'
assert agents > 0, f'No agents seeded'
print(f'Seed OK: flows={flows}, skills={skills}, agents={agents}')
"
```

---

## S2.1 — Callers updated

**As a** pipeline runner,
**I want** `eventlog.py`, `supervisor.py`, `fsm_ops.py`, and `otel_export.py` to call the new `get_db()` and pass `project_root` to helpers,
**So that** pipeline events, state, and runner records are written to the centralized DB under the correct project key.

### Acceptance Criteria

- AC2.1.1: `eventlog.py` has no calls to `get_db(feature_dir)` — all replaced with `get_db()`.
- AC2.1.2: `supervisor.py` has no calls to `get_db(feature_dir)` — all replaced with `get_db()`.
- AC2.1.3: `otel_export.py` has no calls to `get_db(db_path.parent)` — replaced with `get_db()`.
- AC2.1.4: Every helper call in the updated callers passes `project_root` as the second positional argument.
- AC2.1.5: `python -m pytest tests/ -q` produces no new failures versus the Conv 1 baseline.
- AC2.1.6: A simulated pipeline run (can use existing test fixtures) writes events to `~/.pathly/pathly.db`.
- AC2.1.7: **Collision gate** — Two different `project_root` values with the same `feature` name produce isolated rows in `fsm_events`. `read_events(conn, project_root_A, 'security-fixes')` returns zero rows when only `project_root_B` has data for that feature. Verified by `tests/test_db_isolation.py`.

**Verify:**
```bash
python -m pytest tests/ -q
```

---

## S3.1 — Services layer

**As a** route handler author,
**I want** a `services/` package with one module per data domain, callable without Flask,
**So that** HTTP routes stay thin and service logic is independently testable.

### Service modules and their primary methods

| Module | Primary methods |
|---|---|
| `flow_service.py` | `get_flows(project_root=None)`, `get_flow(flow_name)`, `save_flow(flow_dict)` |
| `telemetry_service.py` | `get_events(project_root, feature, since_seq=0)`, `get_event_count(project_root, feature)`, `get_spans(project_root, feature, run_id=None)` |
| `config_service.py` | `get_invocations(project_root, feature)`, `get_agents(project_root=None)`, `get_skills(project_root=None)`, `resolve_skill(skill_name, project_root=None)` |
| `artifact_service.py` | `get_artifacts(project_root, feature)` |

### Acceptance Criteria

- AC3.1.1: All 4 service modules and `__init__.py` exist under `src/pathly_orchestrator/services/`.
- AC3.1.2: No module in `services/` imports from `flask`.
- AC3.1.3: `flow_service.get_flows()` returns a list (may be empty on fresh DB before seed).
- AC3.1.4: `telemetry_service.get_events(project_root, feature)` returns a dict `{total: int, events: list}`.
- AC3.1.5: `config_service.resolve_skill(skill_name, project_root)` returns the project-level override if one exists, otherwise the global definition (local-first resolution).
- AC3.1.6: `config_service.resolve_skill` uses `WHERE (project_root=? OR project_root IS NULL) ORDER BY project_root IS NULL LIMIT 1` query logic.
- AC3.1.7: `python -m pytest tests/test_services.py -v` passes with at least one test per service module.

**Verify:**
```bash
python -m pytest tests/test_services.py -v
```

---

## S4.1 — Feature/flow/skills/agents/traces endpoints

**As a** Studio frontend developer,
**I want** GET endpoints for features, events, invocations, metrics, artifacts, flows, skills, agents, and traces,
**So that** the Studio UI can populate dashboards, the DB Explorer, and the flow builder from live data.

### Endpoints

| Method | Route | Returns |
|---|---|---|
| GET | `/api/features` | `[{feature, project_root, last_state, updated_at}]` |
| GET | `/api/features/<feature>/events` | `{total, events: [...]}` |
| GET | `/api/features/<feature>/invocations` | `[{run_id, stage, agent_role, ...}]` |
| GET | `/api/features/<feature>/metrics` | `{event_count, invocation_count, span_count}` |
| GET | `/api/features/<feature>/artifacts` | `[{stage, artifact_type, path}]` |
| GET | `/api/flows` | `[{name, version, project_root}]` |
| GET | `/api/skills` | `[{skill, filename, natural_language, project_root}]` |
| GET | `/api/agents` | `[{role, name, model, project_root}]` |
| GET | `/api/traces` | `[{trace_id, feature, start_time, ...}]` |

### Acceptance Criteria

- AC4.1.1: `GET /api/flows` returns HTTP 200 with a JSON array when the server is running.
- AC4.1.2: `GET /api/skills` returns HTTP 200 with a JSON array.
- AC4.1.3: `GET /api/agents` returns HTTP 200 with a JSON array.
- AC4.1.4: `GET /api/features` without `project_root` param returns an empty list (not 400).
- AC4.1.5: `GET /api/features/<feature>/events` returns `{total, events}` shape.
- AC4.1.6: `/events/runner` (existing SSE endpoint) is not modified.
- AC4.1.7: All routes return `Content-Type: application/json`.

**Verify:**
```bash
# With server running (python -m pathly_orchestrator.http_server):
curl -s http://127.0.0.1:8765/api/flows | python -m json.tool
curl -s http://127.0.0.1:8765/api/skills | python -m json.tool
curl -s http://127.0.0.1:8765/api/agents | python -m json.tool
```

---

## S4.2 — Override + project endpoints

**As a** Studio user,
**I want** to open a project directory and set skill overrides via the API,
**So that** Studio can track which projects I've opened and apply custom skills per feature/stage.

### Endpoints

| Method | Route | Body |
|---|---|---|
| POST | `/api/skill-override` | `{project_root, feature, run_id, stage, skill_name}` |
| POST | `/project/open` | `{project_root}` |

### Acceptance Criteria

- AC4.2.1: `POST /api/skill-override` with valid body returns HTTP 200 and writes to `skill_overrides` table.
- AC4.2.2: `POST /api/skill-override` with missing `project_root` field returns HTTP 400.
- AC4.2.3: `POST /project/open` with valid `project_root` returns HTTP 200 with `{features: [...]}`.
- AC4.2.4: `POST /project/open` with a non-existent path returns HTTP 200 with `{features: []}` (not an error).
- AC4.2.5: After `POST /api/skill-override`, `GET /api/features/<feature>/metrics` reflects the updated data.

**Verify:**
```bash
curl -s -X POST http://127.0.0.1:8765/project/open \
  -H "Content-Type: application/json" \
  -d '{"project_root": "/tmp/test-project"}' | python -m json.tool

curl -s -X POST http://127.0.0.1:8765/api/skill-override \
  -H "Content-Type: application/json" \
  -d '{"project_root":"/tmp/test-project","feature":"login-flow","run_id":"abc123","stage":"BUILD","skill_name":"pathly-build"}' \
  | python -m json.tool
```
