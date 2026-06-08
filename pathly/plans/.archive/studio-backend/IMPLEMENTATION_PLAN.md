# IMPLEMENTATION_PLAN.md — studio-backend

## Key Decisions

**Decision 1: One DB at `~/.pathly/pathly.db`**
Studio needs to query across multiple projects and features in a single list view.
Per-feature DBs would require the server to scan and open hundreds of file handles.
A single centralized DB with `project_root` as a column eliminates this.

**Decision 2: `project_root` as a column, not a separate DB per project**
Keeping everything in one file means one connection pool, one WAL log, and
no per-project DB management code. SQLite handles concurrent writers via WAL mode.

**Decision 3: Services as thin query wrappers**
Service methods call `get_db()` directly, apply business logic, and return shaped
Python dicts/lists. No Flask imports. This makes services independently testable
with `pytest` and keeps HTTP routes minimal (parse request → call service → jsonify).

**Decision 4: Flask Blueprint for new `/api/*` routes only**
`http_server.py` is 1792 lines with 25+ live routes. Interleaving 20+ new routes directly
creates merge risk and review blindness. A new `api/__init__.py` Blueprint is registered
with one `app.register_blueprint(api_bp)` line — the legacy routes are untouched.
Shared SSE globals (`_runner_clients`, `_menu_clients`) must be imported carefully into
the Blueprint to avoid silent separate-state bugs.

---

## Phase 0 — Pre-flight

**Conv:** 1
**File:** none (read-only baseline)
**Depends on:** nothing
**Enables:** Phase 1

**Done when:**
- Baseline `pytest tests/ -q` result is recorded (pass count and any pre-existing failures noted).
- `python -c "from pathly_orchestrator.db import get_db"` confirms the current import is importable.
- Builder confirms whether `~/.pathly/pathly.db` already exists and records its state.

**Steps:**
1. Run `python -m pytest tests/ -q 2>&1 | tail -10` — record output verbatim, do not fix failures.
2. Run `python -c "from pathly_orchestrator.db import get_db; print('current signature:', get_db.__code__.co_varnames[:get_db.__code__.co_argcount])"`.
3. Run `python -c "import pathlib; p = pathlib.Path.home() / '.pathly' / 'pathly.db'; print('exists:', p.exists())"`.
4. Record all three outputs in a comment block at top of the VERIFY.md file when writing it at end of Conv 1.

---

## Phase 1 — db.py rewrite

**Conv:** 1
**File:** `src/pathly_orchestrator/db.py`
**Depends on:** Phase 0 (baseline recorded)
**Enables:** Phase 2, Phase 3

**Done when:**
- `get_db()` takes no positional arguments.
- DB is created at `~/.pathly/pathly.db`.
- All 12 tables exist after `get_db()` is called.
- `schema_version` table exists with at least one row.
- Migration function runs idempotently (second call does not crash or duplicate tables).
- All 18 helpers (8 updated + 10 new) are importable from `pathly_orchestrator.db`.

**Verify:**
```bash
python -c "
from pathly_orchestrator.db import get_db
conn = get_db()
tables = [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()]
assert len(tables) >= 12, f'Expected >=12 tables, got: {tables}'
mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
assert mode == 'wal', f'Expected WAL, got: {mode}'
ver = conn.execute('SELECT MAX(version) FROM schema_version').fetchone()[0]
assert ver is not None
print(f'OK: {len(tables)} tables, WAL, schema_version={ver}')
"
```

**Callers not touched in this phase:** `fsm_ops.py`, `eventlog.py`, `supervisor.py`, `otel_export.py`

---

## Phase 2 — Seed data

**Conv:** 2
**Files:** `src/pathly_orchestrator/seed.py` (CREATE), `src/pathly_orchestrator/db.py` (add `from pathly_orchestrator.seed import seed_if_empty` call)

> **Architect note:** seed.py is a separate module — YAML/MD parsing has no business inside the SQLite connection module. db.py stays pure persistence.
**Depends on:** Phase 1
**Enables:** Phase 4 (services read seeded catalog)

**Done when:**
- On a fresh DB, `flow_definitions` has rows matching the `.flow.yaml` files in `src/pathly_data/core/flows/`.
- On a fresh DB, `skill_definitions` has rows matching `src/pathly_data/core/skills/**/*.md` files.
- On a fresh DB, `agent_definitions` has rows matching `src/pathly_data/core/agents/**/*.md` files.
- Calling `get_db()` twice produces identical row counts (INSERT OR IGNORE).
- A missing or malformed seed file produces a logged warning and does not crash `get_db()`.

**Verify:**
```bash
python -c "
from pathly_orchestrator.db import get_db
import os, pathlib
db_path = pathlib.Path.home() / '.pathly' / 'pathly.db'
if db_path.exists(): os.remove(db_path)
conn = get_db()
flows = conn.execute('SELECT COUNT(*) FROM flow_definitions').fetchone()[0]
skills = conn.execute('SELECT COUNT(*) FROM skill_definitions').fetchone()[0]
agents = conn.execute('SELECT COUNT(*) FROM agent_definitions').fetchone()[0]
assert flows > 0 and skills > 0 and agents > 0
print(f'Seed OK: flows={flows} skills={skills} agents={agents}')
"
```

---

## Phase 3 — Caller updates

**Conv:** 2
**Files:** `src/pathly_orchestrator/eventlog.py`, `src/pathly_orchestrator/supervisor.py`, `src/pathly_orchestrator/fsm_ops.py`, `src/pathly_orchestrator/otel_export.py`
**Depends on:** Phase 1
**Enables:** Phase 5 (routes use helpers directly)

**Done when:**
- No file contains a call to `get_db(` with any argument.
- Every helper call in the updated files passes `project_root` as the second positional argument.
- `python -m pytest tests/ -q` shows no new failures versus the Conv 1 baseline.

**Per-file change summary:**

| File | Current pattern | New pattern |
|---|---|---|
| `eventlog.py` | `_db.get_db(feature_dir)` | `_db.get_db()` — derive `project_root` from `feature_dir.parent.parent.parent` | **Highest risk** — no project_root in scope today |
| `supervisor.py` | `_db.get_db(feature_dir)` | `_db.get_db()` + use `RunnerState.project_root` | Also rewrite `recover_stale_mirrors` (glob → `SELECT WHERE status='running'`) |
| `otel_export.py` | `_db.get_db(db_path.parent)` | `_db.get_db()` + add project_root to `read_events` call | Simplest — 2 lines |
| `fsm_ops.py` | indirect via `pathly_orchestrator.fsm` | **Likely untouched** — only change if eventlog fix is insufficient | — |

**Collision test (gates Phase 3 done):**
Write `tests/test_db_isolation.py` proving two different `project_root` values with the same `feature` name produce separate rows in `fsm_events` with zero cross-contamination.

**Verify:**
```bash
python -m pytest tests/ -q
python -m pytest tests/test_db_isolation.py -v
```

---

## Phase 4 — Services layer

**Conv:** 3
**File:** `src/pathly_orchestrator/services/` (CREATE 5 files)
**Depends on:** Phase 1 (db helpers exist), Phase 2 (seed data for catalog tests)
**Enables:** Phase 5

> **Architect note:** 4 modules aligned to schema clusters — not 6. Compress event+spans into `telemetry_service`, agent/skill defs+catalog into `config_service`. Split only if a file exceeds ~300 lines.

**Done when:**
- `src/pathly_orchestrator/services/` exists with exactly these files:
  `__init__.py`, `flow_service.py`, `telemetry_service.py`, `config_service.py`, `artifact_service.py`
- No service file imports from `flask`.
- `python -m pytest tests/test_services.py -v` passes with at least one test per service module.

**Method signatures to implement:**

```python
# flow_service.py
def get_flows(project_root=None) -> list[dict]: ...
def get_flow(flow_name: str) -> dict | None: ...
def save_flow(flow_dict: dict) -> None: ...

# telemetry_service.py
def get_events(project_root: str, feature: str, since_seq: int = 0) -> dict: ...
    # returns {total: int, events: list[dict]}
def get_event_count(project_root: str, feature: str) -> int: ...
def get_spans(project_root: str, feature: str, run_id=None) -> list[dict]: ...

# config_service.py
def get_invocations(project_root: str, feature: str) -> list[dict]: ...
def get_agents(project_root=None) -> list[dict]: ...
def get_skills(project_root=None) -> list[dict]: ...
def resolve_skill(skill_name: str, project_root=None) -> dict | None: ...
    # SQL: WHERE (project_root=? OR project_root IS NULL)
    #      ORDER BY project_root IS NULL  -- non-NULL (project-level) sorts first
    #      LIMIT 1

# artifact_service.py
def get_artifacts(project_root: str, feature: str) -> list[dict]: ...
```

**Verify:**
```bash
python -m pytest tests/test_services.py -v
```

---

## Phase 5 — HTTP routes

**Conv:** 4
**Files:** `src/pathly_orchestrator/api/__init__.py` (CREATE), `src/pathly_orchestrator/http_server.py` (1-line MODIFY)
**Depends on:** Phase 4
**Enables:** Studio frontend integration

> **Architect note:** Do NOT add routes directly to http_server.py (1792 lines, 25+ live routes — merge risk). Create a Flask Blueprint in `api/__init__.py`. The only change to `http_server.py` is one `app.register_blueprint(api_bp)` line. Import shared SSE globals carefully to avoid silent separate-state bugs.

**Done when:**
- All routes listed below exist in `src/pathly_orchestrator/api/__init__.py`.
- `http_server.py` has exactly one new line: `app.register_blueprint(api_bp)`.
- `/events/runner` is unchanged.
- `GET /api/flows`, `GET /api/skills`, `GET /api/agents` each return HTTP 200 + valid JSON array.
- `POST /project/open` returns HTTP 200 + `{features: [...]}`.
- `POST /api/skill-override` returns HTTP 200 on valid body, HTTP 400 on missing fields.

**Routes to add:**

| Method | Route | Service call |
|---|---|---|
| GET | `/api/features` | `flow_service.get_flows(project_root=request.args.get('project_root'))` + fsm_state query |
| GET | `/api/features/<feature>/events` | `_svc.get_events(project_root, feature, since_seq)` |
| GET | `/api/features/<feature>/invocations` | `_svc.get_invocations(project_root, feature)` |
| GET | `/api/features/<feature>/metrics` | `_svc.get_event_count` + `_svc.get_invocations` + `_svc.get_spans` |
| GET | `/api/features/<feature>/artifacts` | `_svc.get_artifacts(project_root, feature)` |
| GET | `/api/flows` | `_svc.get_flows()` |
| GET | `/api/skills` | `_svc.get_skills()` |
| GET | `/api/agents` | `_svc.get_agents()` |
| GET | `/api/traces` | `_svc.get_spans(project_root, feature)` with query params |
| POST | `/api/skill-override` | `db.write_skill_override(conn, ...)` |
| POST | `/project/open` | scan `project_root` for plan dirs, return feature list |

**Verify:**
```bash
# Start server in background, then:
curl -s http://127.0.0.1:8765/api/flows | python -m json.tool
curl -s http://127.0.0.1:8765/api/skills | python -m json.tool
curl -s http://127.0.0.1:8765/api/agents | python -m json.tool
```

---

## Dependency Graph

```
Phase 0 (pre-flight)
    │
    ▼
Phase 1 (db.py rewrite) ──────────────────────┐
    │                                          │
    ▼                                          ▼
Phase 2 (seed data)              Phase 3 (caller updates)
    │                                          │
    └─────────────┬─────────────────────────┘
                  ▼
            Phase 4 (services)
                  │
                  ▼
            Phase 5 (HTTP routes)
```
