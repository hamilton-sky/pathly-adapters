# CONVERSATION_PROMPTS.md — studio-backend

---

## Conv 1 — db.py rewrite

Read `pathly/plans/studio-backend/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

**Stories delivered:** S1.1, S1.2
**Phases:** Phase 0 (pre-flight), Phase 1 (db.py rewrite)

---

### Phase 0 — Pre-flight (read-only, do not fix anything)

Run each command and record the output verbatim. Do not fix pre-existing failures.

```bash
# 1. Baseline test count
python -m pytest tests/ -q 2>&1 | tail -10

# 2. Confirm current get_db signature
python -c "from pathly_orchestrator.db import get_db; print('args:', get_db.__code__.co_varnames[:get_db.__code__.co_argcount])"

# 3. Check if centralized DB already exists
python -c "import pathlib; p = pathlib.Path.home() / '.pathly' / 'pathly.db'; print('~/.pathly/pathly.db exists:', p.exists())"
```

Save all three outputs — you will include them in the VERIFY.md file at the end.

---

### Phase 1 — db.py rewrite

**File to rewrite:** `src/pathly_orchestrator/db.py`

Do NOT touch any other file in this conversation. Callers (`fsm_ops.py`, `eventlog.py`, `supervisor.py`, `otel_export.py`) are updated in Conv 2.

#### Requirements

**1. `get_db()` — no arguments**

- Takes no arguments.
- Creates `~/.pathly/` directory if it does not exist (use `Path.home() / '.pathly'`).
- Opens/creates `~/.pathly/pathly.db`.
- Enables WAL mode: `conn.execute("PRAGMA journal_mode=WAL")`.
- Calls `_run_migrations(conn)` before returning.
- Calls `_seed_if_empty(conn)` before returning (seed function is a no-op stub in Conv 1 — implement it properly in Conv 2).
- Returns the open `sqlite3.Connection`.

**2. `_run_migrations(conn)` — idempotent schema creation**

Create a `schema_version` table:
```sql
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
)
```

Create all 12 tables using `CREATE TABLE IF NOT EXISTS`:

```sql
-- Table 1: fsm_events (add project_root column)
CREATE TABLE IF NOT EXISTS fsm_events (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature    TEXT NOT NULL,
    ts         TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload    TEXT NOT NULL
);

-- Table 2: fsm_state
CREATE TABLE IF NOT EXISTS fsm_state (
    project_root TEXT NOT NULL,
    feature    TEXT NOT NULL,
    state_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_root, feature)
);

-- Table 3: runner_state
CREATE TABLE IF NOT EXISTS runner_state (
    project_root TEXT NOT NULL,
    feature    TEXT NOT NULL,
    runner_json TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (project_root, feature)
);

-- Table 4: flow_definitions
CREATE TABLE IF NOT EXISTS flow_definitions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT,
    name       TEXT NOT NULL,
    version    TEXT,
    flow_yaml  TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(name, COALESCE(project_root, ''))
);

-- Table 5: flow_nodes
CREATE TABLE IF NOT EXISTS flow_nodes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_def_id   INTEGER NOT NULL REFERENCES flow_definitions(id),
    node_id       TEXT NOT NULL,
    node_type     TEXT,
    config_json   TEXT
);

-- Table 6: flow_edges
CREATE TABLE IF NOT EXISTS flow_edges (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_def_id   INTEGER NOT NULL REFERENCES flow_definitions(id),
    source_node   TEXT NOT NULL,
    target_node   TEXT NOT NULL,
    label         TEXT
);

-- Table 7: agent_invocations
CREATE TABLE IF NOT EXISTS agent_invocations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    run_id       TEXT,
    stage        TEXT,
    agent_role   TEXT,
    started_at   TEXT,
    finished_at  TEXT,
    tokens_in    INTEGER,
    tokens_out   INTEGER,
    cost_usd     REAL,
    session_id   TEXT,
    summary      TEXT
);

-- Table 8: otel_spans
CREATE TABLE IF NOT EXISTS otel_spans (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    trace_id     TEXT,
    span_id      TEXT,
    parent_span_id TEXT,
    name         TEXT,
    start_time   TEXT,
    end_time     TEXT,
    attributes   TEXT
);

-- Table 9: skill_overrides
CREATE TABLE IF NOT EXISTS skill_overrides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    run_id       TEXT,
    stage        TEXT NOT NULL,
    skill_name   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

-- Table 10: stage_artifacts
CREATE TABLE IF NOT EXISTS stage_artifacts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    run_id       TEXT,
    stage        TEXT,
    artifact_type TEXT,
    path         TEXT,
    created_at   TEXT NOT NULL
);

-- Table 11: skill_definitions
CREATE TABLE IF NOT EXISTS skill_definitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root     TEXT,
    skill            TEXT NOT NULL,
    filename         TEXT,
    natural_language TEXT,
    content          TEXT,
    updated_at       TEXT NOT NULL,
    UNIQUE(skill, COALESCE(project_root, ''))
);

-- Table 12: agent_definitions
CREATE TABLE IF NOT EXISTS agent_definitions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT,
    role         TEXT NOT NULL,
    name         TEXT,
    description  TEXT,
    model        TEXT,
    tools_json   TEXT,
    can_spawn_json TEXT,
    updated_at   TEXT NOT NULL,
    UNIQUE(role, COALESCE(project_root, ''))
);
```

Insert a schema_version row: `INSERT OR IGNORE INTO schema_version VALUES (1, datetime('now'))`.

**3. Updated helper signatures (all 8 existing)**

Update every existing helper to accept `project_root` as the second positional parameter
(after `conn`). Use `project_root` in WHERE clauses and INSERT statements.

```python
def append_event(conn, project_root: str, feature: str, event_dict: dict) -> int:
    # INSERT INTO fsm_events (project_root, feature, ts, event_type, payload) ...
    # Returns the new seq number

def read_events(conn, project_root: str, feature: str, since_seq: int = 0) -> list:
    # SELECT ... WHERE project_root=? AND feature=? AND seq>?

def read_last_agent_done(conn, project_root: str, feature: str) -> dict | None:
    # SELECT ... WHERE project_root=? AND feature=? AND event_type='AGENT_DONE'
    # ORDER BY seq DESC LIMIT 1

def write_state(conn, project_root: str, feature: str, state_dict: dict) -> None:
    # INSERT OR REPLACE INTO fsm_state (project_root, feature, state_json, updated_at)

def read_state(conn, project_root: str, feature: str) -> dict | None:
    # SELECT state_json FROM fsm_state WHERE project_root=? AND feature=?

def write_runner_state(conn, project_root: str, feature: str, runner_dict: dict) -> None:
    # INSERT OR REPLACE INTO runner_state (project_root, feature, runner_json, updated_at)

def read_runner_state(conn, project_root: str, feature: str) -> dict | None:
    # SELECT runner_json FROM runner_state WHERE project_root=? AND feature=?

def mark_stale_runners(conn) -> int:
    # No project_root — global sweep. Returns count of rows updated.
```

**4. New helper signatures (10 new helpers for tables 7–12)**

```python
def upsert_flow_definition(conn, project_root, name: str, version: str, flow_yaml: str) -> int:
    # INSERT OR REPLACE INTO flow_definitions ... returns id

def read_flow_definitions(conn, project_root=None) -> list:
    # If project_root: WHERE project_root=?  else: WHERE project_root IS NULL

def upsert_skill_definition(conn, project_root, skill: str, filename: str,
                             natural_language: str, content: str) -> int:
    # INSERT OR REPLACE INTO skill_definitions ...

def read_skill_definitions(conn, project_root=None) -> list:
    # Same filter pattern as read_flow_definitions

def upsert_agent_definition(conn, project_root, role: str, name: str, description: str,
                             model: str, tools: list, can_spawn: list) -> int:
    # INSERT OR REPLACE INTO agent_definitions ...

def read_agent_definitions(conn, project_root=None) -> list:
    # Same filter pattern

def write_agent_invocation(conn, project_root: str, feature: str, invocation_dict: dict) -> int:
    # INSERT INTO agent_invocations ... returns id

def read_agent_invocations(conn, project_root: str, feature: str) -> list:
    # SELECT * FROM agent_invocations WHERE project_root=? AND feature=?

def write_skill_override(conn, project_root: str, feature: str, run_id: str,
                          stage: str, skill_name: str) -> int:
    # INSERT INTO skill_overrides ... returns id

def read_skill_override(conn, project_root: str, feature: str,
                         stage: str, run_id: str = None) -> dict | None:
    # SELECT ... WHERE project_root=? AND feature=? AND stage=?
    # Optional: AND run_id=?  ORDER BY id DESC LIMIT 1
```

**5. `_seed_if_empty(conn)` stub**

Add this stub only — the full implementation is in Conv 2:

```python
def _seed_if_empty(conn):
    """Populated in Conv 2. No-op stub."""
    pass
```

---

### Verification

Run:
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
conn = get_db()
tables = [r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()]
assert len(tables) >= 12, tables
mode = conn.execute('PRAGMA journal_mode').fetchone()[0]
assert mode == 'wal'
print('PASS:', sorted(tables))
"
```

Also run:
```bash
python -m pytest tests/ -q 2>&1 | tail -10
```
Compare to Phase 0 baseline. If there are new failures, fix them before proceeding.

---

### End of Conv 1 — write VERIFY.md

After all verification passes, write `pathly/plans/studio-backend/VERIFY.md` with:
- First line: `RESULT: PASS`
- Second line: one-line summary of what passed (e.g., "db.py rewritten: 12 tables, WAL, 18 helpers importable")
- Include the Phase 0 pre-flight output as a comment block below the summary

---

## Conv 2 — Seed data + Caller updates

Read `pathly/plans/studio-backend/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

**Stories delivered:** S1.3, S2.1
**Phases:** Phase 2 (seed data), Phase 3 (caller updates)
**Prerequisite:** `pathly/plans/studio-backend/VERIFY.md` must show `RESULT: PASS` from Conv 1.

---

### Phase 2 — Seed data

**Files:** CREATE `src/pathly_orchestrator/seed.py`, then add one import call in `src/pathly_orchestrator/db.py`.

> Seed logic lives in its own module — YAML/MD parsing does not belong in db.py. db.py calls `seed.seed_if_empty(conn)` after migrations.

#### Seed source layout

```
src/pathly_data/core/flows/*.flow.yaml     — 5 flows (explore, test, team, debug, quick-fix)
src/pathly_data/core/agents/**/*.md        — one agent per file; metadata in:
    src/pathly_data/adapters/claude/_meta/<agent-name>.yaml
src/pathly_data/core/skills/**/*.md        — one skill per file; metadata in:
    src/pathly_data/adapters/claude/_meta/<skill-name>_skill.yaml
```

#### Implementation requirements

Create `src/pathly_orchestrator/seed.py` with:

```python
def seed_if_empty(conn):
    """Seed flows, skills, agents from pathly_data if tables are empty."""
    import logging, yaml, json
    from pathlib import Path
    log = logging.getLogger(__name__)

    # Find pathly_data — walk up from this file's location
    this_dir = Path(__file__).resolve().parent
    # Typical layout: src/pathly_orchestrator/ -> src/ -> repo root -> src/pathly_data/
    data_root = None
    for parent in [this_dir.parent, this_dir.parent.parent, this_dir.parent.parent.parent]:
        candidate = parent / 'pathly_data' / 'core'
        if candidate.exists():
            data_root = parent / 'pathly_data'
            break
    if data_root is None:
        log.warning('_seed_if_empty: pathly_data not found, skipping seed')
        return

    # Seed flows
    flows_dir = data_root / 'core' / 'flows'
    if flows_dir.exists():
        for flow_file in flows_dir.glob('*.flow.yaml'):
            try:
                flow_data = yaml.safe_load(flow_file.read_text(encoding='utf-8'))
                name = flow_data.get('flow') or flow_file.stem.replace('.flow', '')
                version = str(flow_data.get('version', '1'))
                upsert_flow_definition(conn, None, name, version, flow_file.read_text(encoding='utf-8'))
            except Exception as e:
                log.warning(f'_seed_if_empty: skipping {flow_file.name}: {e}')

    # Seed agents
    meta_dir = data_root / 'adapters' / 'claude' / '_meta'
    agents_dir = data_root / 'core' / 'agents'
    if agents_dir.exists():
        for agent_file in agents_dir.rglob('*.md'):
            try:
                role = agent_file.stem
                meta_file = meta_dir / f'{role}.yaml' if meta_dir.exists() else None
                meta = {}
                if meta_file and meta_file.exists():
                    meta = yaml.safe_load(meta_file.read_text(encoding='utf-8')) or {}
                upsert_agent_definition(
                    conn, None, role,
                    name=meta.get('name', role),
                    description=meta.get('description', ''),
                    model=meta.get('model', ''),
                    tools=meta.get('tools', []),
                    can_spawn=meta.get('can_spawn', [])
                )
            except Exception as e:
                log.warning(f'_seed_if_empty: skipping agent {agent_file.name}: {e}')

    # Seed skills
    skills_dir = data_root / 'core' / 'skills'
    if skills_dir.exists():
        for skill_file in skills_dir.rglob('*.md'):
            try:
                skill_name = skill_file.stem
                meta_file = meta_dir / f'{skill_name}_skill.yaml' if meta_dir.exists() else None
                meta = {}
                if meta_file and meta_file.exists():
                    meta = yaml.safe_load(meta_file.read_text(encoding='utf-8')) or {}
                content = skill_file.read_text(encoding='utf-8')
                upsert_skill_definition(
                    conn, None,
                    skill=meta.get('skill', skill_name),
                    filename=meta.get('filename', skill_file.name),
                    natural_language=meta.get('natural_language', ''),
                    content=content
                )
            except Exception as e:
                log.warning(f'_seed_if_empty: skipping skill {skill_file.name}: {e}')
```

#### Guard: only seed if tables are empty

Wrap the whole seed body in a check:
```python
count = conn.execute('SELECT COUNT(*) FROM flow_definitions').fetchone()[0]
if count > 0:
    return  # already seeded
```

Then in `src/pathly_orchestrator/db.py`, replace the `_seed_if_empty` stub with:
```python
from pathly_orchestrator.seed import seed_if_empty as _seed_if_empty
```
And call it in `get_db()` after `_run_migrations(conn)`:
```python
_seed_if_empty(conn)
```

---

### Phase 3 — Caller updates

Update exactly these 4 files. For each file, read it first, then apply the minimal changes needed.

#### eventlog.py

Current pattern (4 call sites):
```python
conn = _db.get_db(feature_dir)
```

New pattern:
```python
conn = _db.get_db()
```

Also update every helper call to pass `project_root`. Extract `project_root` from `feature_dir`:
```python
# feature_dir is e.g. /path/to/project/pathly/plans/my-feature
# project_root is the part before /pathly/plans/
project_root = str(feature_dir.parent.parent.parent)
feature = feature_dir.name
```

Update these specific calls:
- `_db.append_event(conn, feature, event)` → `_db.append_event(conn, project_root, feature, event)`
- `_db.write_state(conn, feature, state)` → `_db.write_state(conn, project_root, feature, state)`
- `_db.read_events(conn, feature_dir.name)` → `_db.read_events(conn, project_root, feature)`
- `_db.read_state(conn, feature_dir.name)` → `_db.read_state(conn, project_root, feature)`

#### supervisor.py

Current pattern (4 call sites at lines ~161, ~271, ~293, ~403):
```python
conn = _db.get_db(feature_dir)
```

New pattern:
```python
conn = _db.get_db()
```

`project_root` is already available as `RunnerState.project_root`. Use it directly in all helper calls.

Also update the raw SQL call (supervisor uses `SELECT MAX(seq)` directly):
```python
# Current:
seq = conn.execute('SELECT MAX(seq) FROM fsm_events WHERE feature=?', (feature,)).fetchone()[0]
# New:
seq = conn.execute('SELECT MAX(seq) FROM fsm_events WHERE project_root=? AND feature=?',
                   (project_root, feature)).fetchone()[0]
```

#### otel_export.py

Current:
```python
db_path = Path(project_root) / "pathly" / "plans" / args.feature / "pathly.db"
conn = _db.get_db(db_path.parent)
events = _db.read_events(conn, args.feature)
```

New:
```python
conn = _db.get_db()
events = _db.read_events(conn, project_root, args.feature)
```

Keep `project_root = args.project_root` (or however it is currently derived from CLI args).

#### fsm_ops.py

Trace the `storage_path` usage through `pathly_orchestrator.fsm`. Find every location where
db helpers are called (directly or via `pathly_orchestrator.fsm`). Add `project_root` extraction
from `storage_path` using the same pattern as eventlog.py:
```python
project_root = str(storage_path.parent.parent.parent)
feature = storage_path.name
```

---

### Verification

```bash
python -m pytest tests/ -q 2>&1 | tail -10
```

Compare result to the Conv 1 baseline recorded in VERIFY.md. No new failures allowed.

Also run the seed check:
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

**Collision gate — write `tests/test_db_isolation.py` and run it:**

```python
# tests/test_db_isolation.py
import pathlib, pytest
from unittest.mock import patch

@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    (tmp_path / '.pathly').mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(pathlib.Path, 'home', staticmethod(lambda: tmp_path))

def test_project_root_isolation():
    from pathly_orchestrator.db import get_db, append_event, read_events
    conn = get_db()
    append_event(conn, '/project/alpha', 'security-fixes', {'event_type': 'STAGE_CHANGE', 'ts': '2026-01-01', 'payload': '{}'})
    # project/beta has same feature name but different root
    events_beta = read_events(conn, '/project/beta', 'security-fixes')
    assert events_beta == [], f'Cross-project bleed: {events_beta}'
    events_alpha = read_events(conn, '/project/alpha', 'security-fixes')
    assert len(events_alpha) == 1
```

```bash
python -m pytest tests/test_db_isolation.py -v
```

This test must pass before Conv 2 is done. If it fails, the project_root column is not being applied correctly in `append_event` or `read_events`.

---

### End of Conv 2 — write VERIFY.md

After verification passes, write `pathly/plans/studio-backend/VERIFY.md` with:
- First line: `RESULT: PASS`
- Second line: one-line summary (e.g., "Seed: flows=5 skills=12 agents=13; callers updated; pytest baseline maintained")

---

## Conv 3 — Services layer

Read `pathly/plans/studio-backend/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

**Stories delivered:** S3.1
**Phase:** Phase 4 (services layer + tests)
**Prerequisite:** Conv 2 VERIFY.md shows `RESULT: PASS`.

---

### Phase 4 — Create services/ package

Create `src/pathly_orchestrator/services/` with **4 modules + `__init__.py`**.

> Architect recommendation: 4 files aligned to schema clusters (not 6). Compress events+spans into `telemetry_service`, agent/skill defs+catalog into `config_service`. Split only if a file exceeds ~300 lines.

**Rule: No `flask` imports anywhere in services/.**

#### `__init__.py`

```python
from .flow_service import get_flows, get_flow, save_flow
from .telemetry_service import get_events, get_event_count, get_spans
from .config_service import get_invocations, get_agents, get_skills, resolve_skill
from .artifact_service import get_artifacts

__all__ = [
    'get_flows', 'get_flow', 'save_flow',
    'get_events', 'get_event_count', 'get_spans',
    'get_invocations', 'get_agents', 'get_skills', 'resolve_skill',
    'get_artifacts',
]
```

#### `flow_service.py`

```python
from pathly_orchestrator import db as _db

def get_flows(project_root=None) -> list[dict]:
    conn = _db.get_db()
    return _db.read_flow_definitions(conn, project_root)

def get_flow(flow_name: str) -> dict | None:
    conn = _db.get_db()
    rows = _db.read_flow_definitions(conn)
    return next((r for r in rows if r['name'] == flow_name), None)

def save_flow(flow_dict: dict) -> None:
    conn = _db.get_db()
    _db.upsert_flow_definition(
        conn,
        flow_dict.get('project_root'),
        flow_dict['name'],
        flow_dict.get('version', '1'),
        flow_dict.get('flow_yaml', ''),
    )
```

#### `telemetry_service.py`

```python
from pathly_orchestrator import db as _db

def get_events(project_root: str, feature: str, since_seq: int = 0) -> dict:
    conn = _db.get_db()
    events = _db.read_events(conn, project_root, feature, since_seq)
    return {'total': len(events), 'events': events}

def get_event_count(project_root: str, feature: str) -> int:
    conn = _db.get_db()
    return len(_db.read_events(conn, project_root, feature))

def get_spans(project_root: str, feature: str, run_id=None) -> list[dict]:
    conn = _db.get_db()
    query = 'SELECT * FROM otel_spans WHERE project_root=? AND feature=?'
    params = [project_root, feature]
    if run_id is not None:
        query += ' AND run_id=?'
        params.append(run_id)
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
```

#### `config_service.py`

```python
from pathly_orchestrator import db as _db

def get_invocations(project_root: str, feature: str) -> list[dict]:
    conn = _db.get_db()
    return _db.read_agent_invocations(conn, project_root, feature)

def get_agents(project_root=None) -> list[dict]:
    conn = _db.get_db()
    return _db.read_agent_definitions(conn, project_root)

def get_skills(project_root=None) -> list[dict]:
    conn = _db.get_db()
    return _db.read_skill_definitions(conn, project_root)

def resolve_skill(skill_name: str, project_root=None) -> dict | None:
    conn = _db.get_db()
    if project_root is not None:
        row = conn.execute(
            '''SELECT * FROM skill_definitions
               WHERE skill=? AND (project_root=? OR project_root IS NULL)
               ORDER BY project_root IS NULL
               LIMIT 1''',
            (skill_name, project_root)
        ).fetchone()
    else:
        row = conn.execute(
            'SELECT * FROM skill_definitions WHERE skill=? AND project_root IS NULL LIMIT 1',
            (skill_name,)
        ).fetchone()
    return dict(row) if row else None
```

#### `artifact_service.py`

```python
from pathly_orchestrator import db as _db

def get_artifacts(project_root: str, feature: str) -> list[dict]:
    conn = _db.get_db()
    rows = conn.execute(
        'SELECT * FROM stage_artifacts WHERE project_root=? AND feature=?',
        (project_root, feature)
    ).fetchall()
    return [dict(r) for r in rows]
```

---

### Write tests/test_services.py

Create `tests/test_services.py` with at least one test per service module.
Each test must call the service function directly (no Flask test client).
Use a tmp DB path to avoid polluting `~/.pathly/pathly.db`:

```python
import os, sqlite3, pathlib, pytest
from unittest.mock import patch

# Point get_db() at a temp file for testing
@pytest.fixture(autouse=True)
def tmp_db(tmp_path, monkeypatch):
    db_file = tmp_path / 'test.db'
    import pathly_orchestrator.db as _db
    # Patch Path.home() so get_db() writes to tmp_path/.pathly/
    fake_home = tmp_path
    monkeypatch.setattr(pathlib.Path, 'home', staticmethod(lambda: fake_home))
    # Ensure the subdir exists
    (tmp_path / '.pathly').mkdir(parents=True, exist_ok=True)
    yield tmp_path

# --- flow_service tests ---
def test_get_flows_empty():
    from pathly_orchestrator.services import get_flows
    result = get_flows()
    assert isinstance(result, list)

def test_save_and_get_flow():
    from pathly_orchestrator.services import save_flow, get_flow
    save_flow({'name': 'test-flow', 'version': '1', 'flow_yaml': 'flow: test-flow'})
    result = get_flow('test-flow')
    assert result is not None
    assert result['name'] == 'test-flow'

# --- telemetry_service tests ---
def test_get_events_empty():
    from pathly_orchestrator.services import get_events
    result = get_events('/tmp/proj', 'my-feature')
    assert result == {'total': 0, 'events': []}

def test_get_spans_empty():
    from pathly_orchestrator.services import get_spans
    result = get_spans('/tmp/proj', 'my-feature')
    assert result == []

# --- config_service tests ---
def test_get_agents_empty():
    from pathly_orchestrator.services import get_agents
    result = get_agents()
    assert isinstance(result, list)

def test_get_invocations_empty():
    from pathly_orchestrator.services import get_invocations
    result = get_invocations('/tmp/proj', 'my-feature')
    assert isinstance(result, list)

def test_get_skills_empty():
    from pathly_orchestrator.services import get_skills
    result = get_skills()
    assert isinstance(result, list)

def test_resolve_skill_missing():
    from pathly_orchestrator.services import resolve_skill
    result = resolve_skill('nonexistent-skill')
    assert result is None

def test_resolve_skill_local_first():
    from pathly_orchestrator.services import resolve_skill
    from pathly_orchestrator.db import get_db, upsert_skill_definition
    conn = get_db()
    upsert_skill_definition(conn, None, 'my-skill', 'my-skill.md', 'global', 'global content')
    upsert_skill_definition(conn, '/tmp/proj', 'my-skill', 'my-skill.md', 'local', 'local content')
    result = resolve_skill('my-skill', project_root='/tmp/proj')
    assert result['natural_language'] == 'local'

# --- artifact_service tests ---
def test_get_artifacts_empty():
    from pathly_orchestrator.services import get_artifacts
    result = get_artifacts('/tmp/proj', 'my-feature')
    assert result == []
```

---

### Verification

```bash
python -m pytest tests/test_services.py -v
```

All tests must pass. If any test fails, fix the service implementation before writing VERIFY.md.

---

### End of Conv 3 — write VERIFY.md

After verification passes, write `pathly/plans/studio-backend/VERIFY.md` with:
- First line: `RESULT: PASS`
- Second line: one-line summary (e.g., "Services layer: 5 files created, test_services.py: 11 passed")

---

## Conv 4 — HTTP routes

Read `pathly/plans/studio-backend/FEATURE_INDEX.md` first to orient yourself and verify codebase paths.

**Stories delivered:** S4.1, S4.2
**Phase:** Phase 5 (HTTP routes)
**Prerequisite:** Conv 3 VERIFY.md shows `RESULT: PASS`.

---

### Phase 5 — HTTP routes via Blueprint

**CREATE** `src/pathly_orchestrator/api/__init__.py` — all new routes go here.
**MODIFY** `src/pathly_orchestrator/http_server.py` — add exactly ONE line.

Do NOT add routes directly to `http_server.py` (1792 lines, 25+ live routes). Instead:

1. Create the Blueprint file:

```python
# src/pathly_orchestrator/api/__init__.py
from flask import Blueprint, request, jsonify
from pathly_orchestrator import services as _svc
from pathly_orchestrator import db as _db

api_bp = Blueprint('api', __name__, url_prefix='')
```

2. In `src/pathly_orchestrator/http_server.py`, find the line `app = Flask(__name__)` and add directly after it:
```python
from pathly_orchestrator.api import api_bp
app.register_blueprint(api_bp)
```

All routes below are defined in `api/__init__.py` using `@api_bp.route(...)` instead of `@app.route(...)`.

---

#### GET /api/features

```python
@api_bp.route('/api/features', methods=['GET'])
def api_features():
    project_root = request.args.get('project_root')
    if not project_root:
        return jsonify([]), 200
    conn = _db.get_db()
    rows = conn.execute(
        'SELECT DISTINCT feature FROM fsm_state WHERE project_root=?',
        (project_root,)
    ).fetchall()
    result = []
    for row in rows:
        feature = row[0]
        state = _db.read_state(conn, project_root, feature) or {}
        result.append({
            'feature': feature,
            'project_root': project_root,
            'last_state': state.get('current_state'),
            'updated_at': state.get('updated_at'),
        })
    return jsonify(result), 200
```

---

#### GET /api/features/<feature>/events

```python
@api_bp.route('/api/features/<feature>/events', methods=['GET'])
def api_feature_events(feature):
    project_root = request.args.get('project_root', '')
    since_seq = int(request.args.get('since_seq', 0))
    result = _svc.get_events(project_root, feature, since_seq)
    return jsonify(result), 200
```

---

#### GET /api/features/<feature>/invocations

```python
@api_bp.route('/api/features/<feature>/invocations', methods=['GET'])
def api_feature_invocations(feature):
    project_root = request.args.get('project_root', '')
    result = _svc.get_invocations(project_root, feature)
    return jsonify(result), 200
```

---

#### GET /api/features/<feature>/metrics

```python
@api_bp.route('/api/features/<feature>/metrics', methods=['GET'])
def api_feature_metrics(feature):
    project_root = request.args.get('project_root', '')
    event_count = _svc.get_event_count(project_root, feature)
    invocations = _svc.get_invocations(project_root, feature)
    spans = _svc.get_spans(project_root, feature)
    return jsonify({
        'event_count': event_count,
        'invocation_count': len(invocations),
        'span_count': len(spans),
    }), 200
```

---

#### GET /api/features/<feature>/artifacts

```python
@api_bp.route('/api/features/<feature>/artifacts', methods=['GET'])
def api_feature_artifacts(feature):
    project_root = request.args.get('project_root', '')
    result = _svc.get_artifacts(project_root, feature)
    return jsonify(result), 200
```

---

#### GET /api/flows

```python
@api_bp.route('/api/flows', methods=['GET'])
def api_flows():
    project_root = request.args.get('project_root')
    result = _svc.get_flows(project_root)
    return jsonify(result), 200
```

---

#### POST /api/flows

Body example:
```json
{"name": "my-flow", "nodes": [...], "edges": [...]}
```

```python
@api_bp.route('/api/flows', methods=['POST'])
def api_flows_post():
    body = request.get_json(force=True) or {}
    if not body.get('name'):
        return jsonify({'error': 'name required'}), 400
    _svc.save_flow(body)
    return jsonify({'ok': True}), 200
```

---

#### GET /api/skills

```python
@api_bp.route('/api/skills', methods=['GET'])
def api_skills():
    project_root = request.args.get('project_root')
    result = _svc.get_skills(project_root)
    return jsonify(result), 200
```

---

#### GET /api/agents

```python
@api_bp.route('/api/agents', methods=['GET'])
def api_agents():
    project_root = request.args.get('project_root')
    result = _svc.get_agents(project_root)
    return jsonify(result), 200
```

---

#### GET /api/traces

```python
@api_bp.route('/api/traces', methods=['GET'])
def api_traces():
    project_root = request.args.get('project_root', '')
    feature = request.args.get('feature', '')
    run_id = request.args.get('run_id')
    result = _svc.get_spans(project_root, feature, run_id)
    return jsonify(result), 200
```

---

#### POST /api/skill-override

Body example:
```json
{
  "project_root": "/path/to/project",
  "feature": "login-flow",
  "run_id": "abc123",
  "stage": "BUILD",
  "skill_name": "pathly-build"
}
```

```python
@api_bp.route('/api/skill-override', methods=['POST'])
def api_skill_override():
    body = request.get_json(force=True) or {}
    required = ['project_root', 'feature', 'stage', 'skill_name']
    for field in required:
        if not body.get(field):
            return jsonify({'error': f'{field} required'}), 400
    conn = _db.get_db()
    _db.write_skill_override(
        conn,
        body['project_root'],
        body['feature'],
        body.get('run_id'),
        body['stage'],
        body['skill_name'],
    )
    return jsonify({'ok': True}), 200
```

---

#### POST /project/open

Body example:
```json
{"project_root": "/path/to/project"}
```

```python
@api_bp.route('/project/open', methods=['POST'])
def project_open():
    body = request.get_json(force=True) or {}
    project_root = body.get('project_root', '')
    from pathlib import Path
    features = []
    plans_dir = Path(project_root) / 'pathly' / 'plans'
    if plans_dir.exists():
        for entry in sorted(plans_dir.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.'):
                features.append(entry.name)
    return jsonify({'features': features}), 200
```

---

### Verification

Start the HTTP server in one terminal:
```bash
python -m pathly_orchestrator.http_server
```

In a second terminal, run:
```bash
curl -s http://127.0.0.1:8765/api/flows | python -m json.tool
curl -s http://127.0.0.1:8765/api/skills | python -m json.tool
curl -s http://127.0.0.1:8765/api/agents | python -m json.tool
```

All three must return HTTP 200 and valid JSON arrays.

Also verify the POST endpoints:
```bash
curl -s -X POST http://127.0.0.1:8765/project/open \
  -H "Content-Type: application/json" \
  -d '{"project_root": "/tmp/test-project"}' | python -m json.tool

curl -s -X POST http://127.0.0.1:8765/api/skill-override \
  -H "Content-Type: application/json" \
  -d '{"project_root":"/tmp/test-project","feature":"login-flow","run_id":"abc123","stage":"BUILD","skill_name":"pathly-build"}' \
  | python -m json.tool
```

---

### End of Conv 4 — write VERIFY.md

After verification passes, write `pathly/plans/studio-backend/VERIFY.md` with:
- First line: `RESULT: PASS`
- Second line: one-line summary (e.g., "HTTP routes: 11 endpoints registered, GET /api/flows + /api/skills + /api/agents return 200 JSON")
