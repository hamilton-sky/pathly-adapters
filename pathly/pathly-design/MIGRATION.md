# Pathly — Migration Plan

How to migrate from the current backend to the new single-DB architecture.

---

## What the current code does

### `db.py` (current)
- `get_db(feature_dir: str) → sqlite3.Connection`
  - Opens `<feature_dir>/pathly.db` — one DB per feature directory
  - Each feature has its own SQLite file
- Tables: `fsm_events`, `fsm_state`, `runner_state` (tables 1-3 only)
- Helpers: `append_event`, `read_events`, `write_state`, `read_state`, `write_runner_state`, `read_runner_state`, `mark_stale_runners`

### `fsm_ops.py` (current)
- Takes `feature_dir` and opens DB via `get_db(feature_dir)`
- All state keyed by `feature_dir` path

### `supervisor.py` (current)
- Receives `feature_dir` from runner start
- Passes to `get_db(feature_dir)` on every DB call

### `http_server.py` (current)
- Routes pass `feature_dir` into FSM and DB functions
- No `/api/*` routes yet

---

## Target state

### `db.py` (new)
- `get_db() → sqlite3.Connection`
  - Always opens `~/.pathly/pathly.db`
  - No arguments
- Tables: all 12 (tables 1-3 with `project_root` added, tables 4-12 new)
- All helpers take `(project_root: str, feature: str)` instead of just `(feature_dir)`

---

## Step-by-step migration

### Step 1 — Update `get_db()`
```python
# BEFORE
def get_db(feature_dir: str) -> sqlite3.Connection:
    path = os.path.join(feature_dir, "pathly.db")
    conn = sqlite3.connect(path)
    ...

# AFTER
import os, pathlib

APP_DB_PATH = pathlib.Path.home() / ".pathly" / "pathly.db"

def get_db() -> sqlite3.Connection:
    APP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(APP_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
```

### Step 2 — Update `_SCHEMA_SQL` in `db.py`
Replace with the full schema from `schema_all.sql`.
Key changes to existing tables:
```sql
-- fsm_events: add project_root column + update indexes
ALTER TABLE fsm_events ADD COLUMN project_root TEXT NOT NULL DEFAULT '';

-- fsm_state: change PK from (feature) to (project_root, feature)
-- Cannot ALTER PRIMARY KEY in SQLite — must recreate the table:
CREATE TABLE fsm_state_new (
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    current      TEXT NOT NULL,
    ...
    PRIMARY KEY (project_root, feature)
);
INSERT INTO fsm_state_new SELECT '', feature, current, ... FROM fsm_state;
DROP TABLE fsm_state;
ALTER TABLE fsm_state_new RENAME TO fsm_state;

-- runner_state: same pattern
CREATE TABLE runner_state_new (
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    ...
    PRIMARY KEY (project_root, feature)
);
INSERT INTO runner_state_new SELECT '', feature, ... FROM runner_state;
DROP TABLE runner_state;
ALTER TABLE runner_state_new RENAME TO runner_state;
```

Use a `schema_version` table to track migration state:
```sql
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);
```

### Step 3 — Update all `db.py` helper signatures
```python
# BEFORE
def write_state(feature_dir: str, state: dict): ...
def read_state(feature_dir: str) -> dict: ...
def append_event(feature_dir: str, event: dict): ...

# AFTER
def write_state(project_root: str, feature: str, state: dict): ...
def read_state(project_root: str, feature: str) -> dict: ...
def append_event(project_root: str, feature: str, event: dict): ...
```

All SQL in helpers: add `WHERE project_root=? AND feature=?`

### Step 4 — Update `fsm_ops.py`
```python
# BEFORE
def next_action(feature_dir: str, ...):
    db = get_db(feature_dir)
    state = read_state(feature_dir)

# AFTER
def next_action(project_root: str, feature: str, ...):
    db = get_db()
    state = read_state(project_root, feature)
```

### Step 5 — Update `supervisor.py`
```python
# BEFORE
feature_dir = f"pathly/plans/{topic}"
db = get_db(feature_dir)

# AFTER
project_root = runner_config["project_root"]
feature = runner_config["feature"]
db = get_db()
```

### Step 6 — Update `http_server.py`
- All existing routes: extract `project_root` from request body
- Add all `/api/*` routes (see API_CONTRACTS.md)
- Startup: call `_ensure_schema()` and `_seed_if_empty()`

### Step 7 — Add `services/` directory
Create `src/pathly_orchestrator/services/` with:
- `flow_service.py`
- `event_service.py`
- `agent_service.py`
- `span_service.py`
- `artifact_service.py`

Each service calls `get_db()` directly (no connection passing).

### Step 8 — Migrate existing data (if any)
For users with existing per-feature DB files:
```python
def migrate_legacy_data(project_root: str):
    """
    Find all pathly/plans/*/pathly.db files under project_root.
    Copy their rows into the new single DB with project_root set.
    """
    import glob
    pattern = os.path.join(project_root, "pathly", "plans", "*", "pathly.db")
    for legacy_db_path in glob.glob(pattern):
        feature = os.path.basename(os.path.dirname(legacy_db_path))
        _migrate_feature_db(legacy_db_path, project_root, feature)
```

---

## Schema version tracking

Add to `db.py`:
```python
CURRENT_SCHEMA_VERSION = 2

def _ensure_schema(db):
    db.executescript(SCHEMA_SQL)  # CREATE TABLE IF NOT EXISTS for all 12 tables
    db.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER)")
    row = db.execute("SELECT version FROM schema_version").fetchone()
    current = row[0] if row else 0
    if current < CURRENT_SCHEMA_VERSION:
        _run_migrations(db, current)
        db.execute("DELETE FROM schema_version")
        db.execute("INSERT INTO schema_version VALUES (?)", (CURRENT_SCHEMA_VERSION,))
        db.commit()

def _run_migrations(db, from_version: int):
    if from_version < 1:
        # v1: initial schema
        pass
    if from_version < 2:
        # v2: add project_root, recreate fsm_state + runner_state PKs
        _migrate_v1_to_v2(db)
```

---

## Files changed summary

| File | Change type | What changes |
|---|---|---|
| `db.py` | Major rewrite | `get_db()` signature, schema, all helper signatures |
| `fsm_ops.py` | Signature update | `(feature_dir)` → `(project_root, feature)` |
| `supervisor.py` | Signature update | read `project_root` from runner config |
| `http_server.py` | Add routes | all `/api/*` routes + startup seed |
| `eventlog.py` | Signature update | `(feature_dir)` → `(project_root, feature)` |
| `otel_export.py` | Signature update | add `project_root` to span writes |
| `services/` | New directory | all service files |
| `skill_catalog.py` | Update | `resolve_skill(file_name, project_root)` with local-first SQL |
