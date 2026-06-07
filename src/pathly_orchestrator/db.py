"""
SQLite persistence layer for pathly_orchestrator.

Central database at ~/.pathly/pathly.db shared across all projects.
WAL mode + NORMAL sync allows concurrent readers alongside a single writer.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_conn_cache: dict[str, sqlite3.Connection] = {}
_cache_lock = threading.Lock()
# Per-connection write lock keyed by id(conn).
# Python's sqlite3 module is not thread-safe for concurrent writes on a shared
# connection even with check_same_thread=False; this serialises them.
_write_locks: dict[int, threading.Lock] = {}

# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

def _run_migrations(conn: sqlite3.Connection) -> None:
    """Idempotent schema creation for all 12 tables + schema_version."""
    conn.executescript("""
CREATE TABLE IF NOT EXISTS schema_version (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fsm_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    ts           TEXT NOT NULL,
    event_type   TEXT NOT NULL,
    payload      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fsm_state (
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    state_json   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (project_root, feature)
);

CREATE TABLE IF NOT EXISTS runner_state (
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    runner_json  TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (project_root, feature)
);

CREATE TABLE IF NOT EXISTS flow_definitions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT,
    name         TEXT NOT NULL,
    version      TEXT,
    flow_yaml    TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS flow_nodes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_def_id INTEGER NOT NULL REFERENCES flow_definitions(id),
    node_id     TEXT NOT NULL,
    node_type   TEXT,
    config_json TEXT
);

CREATE TABLE IF NOT EXISTS flow_edges (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_def_id INTEGER NOT NULL REFERENCES flow_definitions(id),
    source_node TEXT NOT NULL,
    target_node TEXT NOT NULL,
    label       TEXT
);

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

CREATE TABLE IF NOT EXISTS otel_spans (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root   TEXT NOT NULL,
    feature        TEXT NOT NULL,
    trace_id       TEXT,
    span_id        TEXT,
    parent_span_id TEXT,
    name           TEXT,
    start_time     TEXT,
    end_time       TEXT,
    attributes     TEXT
);

CREATE TABLE IF NOT EXISTS skill_overrides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    run_id       TEXT,
    stage        TEXT NOT NULL,
    skill_name   TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stage_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root  TEXT NOT NULL,
    feature       TEXT NOT NULL,
    run_id        TEXT,
    stage         TEXT,
    artifact_type TEXT,
    path          TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_definitions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root     TEXT,
    skill            TEXT NOT NULL,
    filename         TEXT,
    natural_language TEXT,
    content          TEXT,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agent_definitions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root   TEXT,
    role           TEXT NOT NULL,
    name           TEXT,
    description    TEXT,
    model          TEXT,
    tools_json     TEXT,
    can_spawn_json TEXT,
    updated_at     TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_version VALUES (1, datetime('now'));

CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_def_name_global
    ON flow_definitions(name) WHERE project_root IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_def_name_proj
    ON flow_definitions(name, project_root) WHERE project_root IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_def_name_global
    ON skill_definitions(skill) WHERE project_root IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_def_name_proj
    ON skill_definitions(skill, project_root) WHERE project_root IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_def_role_global
    ON agent_definitions(role) WHERE project_root IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_def_role_proj
    ON agent_definitions(role, project_root) WHERE project_root IS NOT NULL;
""")
    conn.commit()


# ---------------------------------------------------------------------------
# Seed stub (implemented in Conv 2)
# ---------------------------------------------------------------------------

def _seed_if_empty(conn: sqlite3.Connection) -> None:
    """Populated in Conv 2. No-op stub."""
    pass


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def get_db(_deprecated_path=None) -> sqlite3.Connection:
    """Return a cached sqlite3.Connection for ~/.pathly/pathly.db.

    _deprecated_path is accepted for backward compat but ignored.
    Always opens ~/.pathly/pathly.db (resolved at call time so tests can patch Path.home()).
    """
    db_dir = Path.home() / ".pathly"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = str(db_dir / "pathly.db")

    with _cache_lock:
        if db_path in _conn_cache:
            return _conn_cache[db_path]
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _run_migrations(conn)
        _seed_if_empty(conn)
        _conn_cache[db_path] = conn
        conn_id: int = id(conn)
        _write_locks[conn_id] = threading.Lock()
        return conn


def _get_write_lock(conn: sqlite3.Connection) -> threading.Lock:
    """Return the write lock for *conn*, keyed by connection identity."""
    conn_id: int = id(conn)
    with _cache_lock:
        if conn_id not in _write_locks:
            _write_locks[conn_id] = threading.Lock()
        return _write_locks[conn_id]


# ---------------------------------------------------------------------------
# fsm_events helpers
# ---------------------------------------------------------------------------

def append_event(
    conn: sqlite3.Connection, project_root: str, feature: str, event_dict: dict
) -> int:
    """Insert *event_dict* into fsm_events. Returns the new seq (lastrowid)."""
    event_type = event_dict.get("type", event_dict.get("event_type", ""))
    ts = event_dict.get("ts", "")
    payload = json.dumps(event_dict)
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO fsm_events (project_root, feature, ts, event_type, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_root, feature, ts, event_type, payload),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_events(
    conn: sqlite3.Connection, project_root: str, feature: str, since_seq: int = 0
) -> list[dict]:
    """Return all events for *project_root*/*feature* with seq > *since_seq*, ordered by seq."""
    rows = conn.execute(
        "SELECT seq, payload FROM fsm_events "
        "WHERE project_root=? AND feature=? AND seq>? ORDER BY seq ASC",
        (project_root, feature, since_seq),
    ).fetchall()
    result = []
    for row in rows:
        event = json.loads(row["payload"])
        event["seq"] = row["seq"]
        result.append(event)
    return result


def read_last_agent_done(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> dict | None:
    """Return the payload of the most recent AGENT_DONE event, or None."""
    row = conn.execute(
        "SELECT payload FROM fsm_events "
        "WHERE project_root=? AND feature=? AND event_type='AGENT_DONE' "
        "ORDER BY seq DESC LIMIT 1",
        (project_root, feature),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload"])


# ---------------------------------------------------------------------------
# fsm_state helpers
# ---------------------------------------------------------------------------

def write_state(
    conn: sqlite3.Connection, project_root: str, feature: str, state_dict: dict
) -> None:
    """Upsert *state_dict* into fsm_state as JSON."""
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR REPLACE INTO fsm_state (project_root, feature, state_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                project_root,
                feature,
                json.dumps(state_dict),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def read_state(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> dict | None:
    """Return the fsm_state row for *project_root*/*feature* as a dict, or None."""
    row = conn.execute(
        "SELECT state_json FROM fsm_state WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["state_json"])


# ---------------------------------------------------------------------------
# runner_state helpers
# ---------------------------------------------------------------------------

def write_runner_state(
    conn: sqlite3.Connection, project_root: str, feature: str, runner_dict: dict
) -> None:
    """Upsert *runner_dict* into runner_state as JSON."""
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR REPLACE INTO runner_state "
            "(project_root, feature, runner_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                project_root,
                feature,
                json.dumps(runner_dict),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def read_runner_state(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> dict | None:
    """Return the runner_state row for *project_root*/*feature* as a dict, or None."""
    row = conn.execute(
        "SELECT runner_json FROM runner_state WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["runner_json"])


def mark_stale_runners(conn: sqlite3.Connection) -> int:
    """Set status='error' for all runner_state rows where runner_json contains status='running'.

    Returns the number of rows updated.
    """
    with _get_write_lock(conn):
        rows = conn.execute("SELECT project_root, feature, runner_json FROM runner_state").fetchall()
        updated = 0
        for row in rows:
            try:
                d = json.loads(row["runner_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            if d.get("status") == "running":
                d["status"] = "error"
                conn.execute(
                    "UPDATE runner_state SET runner_json=? WHERE project_root=? AND feature=?",
                    (json.dumps(d), row["project_root"], row["feature"]),
                )
                updated += 1
        conn.commit()
        return updated


# ---------------------------------------------------------------------------
# flow_definitions helpers
# ---------------------------------------------------------------------------

def upsert_flow_definition(
    conn: sqlite3.Connection,
    project_root,
    name: str,
    version: str,
    flow_yaml: str,
) -> int:
    """Upsert a flow definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO flow_definitions "
            "(project_root, name, version, flow_yaml, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                project_root,
                name,
                version,
                flow_yaml,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_flow_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return flow definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM flow_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM flow_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# skill_definitions helpers
# ---------------------------------------------------------------------------

def upsert_skill_definition(
    conn: sqlite3.Connection,
    project_root,
    skill: str,
    filename: str,
    natural_language: str,
    content: str,
) -> int:
    """Upsert a skill definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO skill_definitions "
            "(project_root, skill, filename, natural_language, content, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_root,
                skill,
                filename,
                natural_language,
                content,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_skill_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return skill definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM skill_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM skill_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# agent_definitions helpers
# ---------------------------------------------------------------------------

def upsert_agent_definition(
    conn: sqlite3.Connection,
    project_root,
    role: str,
    name: str,
    description: str,
    model: str,
    tools: list,
    can_spawn: list,
) -> int:
    """Upsert an agent definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO agent_definitions "
            "(project_root, role, name, description, model, tools_json, can_spawn_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root,
                role,
                name,
                description,
                model,
                json.dumps(tools),
                json.dumps(can_spawn),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_agent_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return agent definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM agent_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# agent_invocations helpers
# ---------------------------------------------------------------------------

def write_agent_invocation(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    invocation_dict: dict,
) -> int:
    """Insert an agent invocation record. Returns the new id."""
    d = invocation_dict
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO agent_invocations "
            "(project_root, feature, run_id, stage, agent_role, started_at, finished_at, "
            " tokens_in, tokens_out, cost_usd, session_id, summary) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root,
                feature,
                d.get("run_id"),
                d.get("stage"),
                d.get("agent_role"),
                d.get("started_at"),
                d.get("finished_at"),
                d.get("tokens_in"),
                d.get("tokens_out"),
                d.get("cost_usd"),
                d.get("session_id"),
                d.get("summary"),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_agent_invocations(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> list[dict]:
    """Return all agent invocations for *project_root*/*feature*."""
    rows = conn.execute(
        "SELECT * FROM agent_invocations WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# skill_overrides helpers
# ---------------------------------------------------------------------------

def write_skill_override(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    run_id: str | None,
    stage: str,
    skill_name: str,
) -> int:
    """Insert a skill override record. Returns the new id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO skill_overrides "
            "(project_root, feature, run_id, stage, skill_name, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_root,
                feature,
                run_id,
                stage,
                skill_name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_skill_override(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    stage: str,
    run_id: str | None = None,
) -> dict | None:
    """Return the most recent skill override for *project_root*/*feature*/*stage*, or None."""
    if run_id is not None:
        row = conn.execute(
            "SELECT * FROM skill_overrides "
            "WHERE project_root=? AND feature=? AND stage=? AND run_id=? "
            "ORDER BY id DESC LIMIT 1",
            (project_root, feature, stage, run_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM skill_overrides "
            "WHERE project_root=? AND feature=? AND stage=? "
            "ORDER BY id DESC LIMIT 1",
            (project_root, feature, stage),
        ).fetchone()
    return dict(row) if row else None
