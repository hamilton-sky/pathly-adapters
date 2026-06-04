"""
SQLite persistence layer for pathly_orchestrator.

One database file per feature directory: <feature_dir>/pathly.db
WAL mode + NORMAL sync allows concurrent readers alongside a single writer.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

_conn_cache: dict[str, sqlite3.Connection] = {}
_cache_lock = threading.Lock()
# Per-connection write lock keyed by id(conn).
# Python's sqlite3 module is not thread-safe for concurrent writes on a shared
# connection even with check_same_thread=False; this serialises them.
_write_locks: dict[int, threading.Lock] = {}

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS fsm_events (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    feature          TEXT    NOT NULL,
    type             TEXT    NOT NULL,
    ts               TEXT    NOT NULL,
    schema_version   INTEGER DEFAULT 1,
    payload          TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_feature ON fsm_events(feature, seq);

CREATE TABLE IF NOT EXISTS fsm_state (
    feature              TEXT PRIMARY KEY,
    current              TEXT NOT NULL,
    rigor                TEXT,
    current_conversation INTEGER,
    retry_count_by_key   TEXT,
    iteration_by_stage   TEXT,
    updated_at           TEXT NOT NULL,
    conv_start_sha       TEXT,
    convs_total          INTEGER,
    convs_done           INTEGER,
    build_baseline       TEXT,
    extra                TEXT
);

CREATE TABLE IF NOT EXISTS runner_state (
    feature          TEXT PRIMARY KEY,
    topic            TEXT,
    flow             TEXT,
    project_root     TEXT,
    model            TEXT,
    timeout          INTEGER,
    run_id           TEXT,
    status           TEXT    DEFAULT 'idle',
    current_state    TEXT    DEFAULT '',
    current_adapter  TEXT,
    iterations       INTEGER DEFAULT 0,
    max_iterations   INTEGER,
    cost_usd_so_far  REAL    DEFAULT 0.0,
    max_cost_usd     REAL,
    autonomy         TEXT    DEFAULT '{}',
    pending_menu     TEXT,
    error_kind       TEXT,
    open_session     TEXT,
    updated_at       TEXT
);
"""


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA_SQL)
    conn.commit()


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def get_db(feature_dir: Path) -> sqlite3.Connection:
    """Return a cached sqlite3.Connection for *feature_dir*/pathly.db.

    Opens the DB on first call; returns the cached object on subsequent calls
    for the same absolute path.  WAL mode and NORMAL synchronous pragma are set
    on the first open so concurrent readers never block the writer.
    """
    db_path = str(feature_dir.resolve() / "pathly.db")
    with _cache_lock:
        if db_path in _conn_cache:
            return _conn_cache[db_path]
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        _init_schema(conn)
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

def append_event(conn: sqlite3.Connection, feature: str, event_dict: dict) -> int:
    """Insert *event_dict* into fsm_events.  Returns the new seq (lastrowid)."""
    event_type = event_dict.get("type", "")
    ts = event_dict.get("ts", "")
    schema_version = event_dict.get("schema_version", 1)
    payload = json.dumps(event_dict)
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO fsm_events (feature, type, ts, schema_version, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (feature, event_type, ts, schema_version, payload),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_events(
    conn: sqlite3.Connection, feature: str, since_seq: int = 0
) -> list[dict]:
    """Return all events for *feature* with seq > *since_seq*, ordered by seq."""
    rows = conn.execute(
        "SELECT seq, payload FROM fsm_events "
        "WHERE feature=? AND seq>? ORDER BY seq ASC",
        (feature, since_seq),
    ).fetchall()
    result = []
    for row in rows:
        event = json.loads(row["payload"])
        event["seq"] = row["seq"]
        result.append(event)
    return result


def read_last_agent_done(
    conn: sqlite3.Connection, feature: str
) -> dict | None:
    """Return the payload of the most recent AGENT_DONE event, or None."""
    row = conn.execute(
        "SELECT payload FROM fsm_events "
        "WHERE feature=? AND type='AGENT_DONE' ORDER BY seq DESC LIMIT 1",
        (feature,),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload"])


# ---------------------------------------------------------------------------
# fsm_state helpers
# ---------------------------------------------------------------------------

_FSM_STATE_JSON_FIELDS = ("retry_count_by_key", "iteration_by_stage", "build_baseline", "extra")


def write_state(conn: sqlite3.Connection, feature: str, state_dict: dict) -> None:
    """Upsert *state_dict* into fsm_state."""
    d = dict(state_dict)
    d["feature"] = feature
    for field in _FSM_STATE_JSON_FIELDS:
        if field in d and not isinstance(d[field], str) and d[field] is not None:
            d[field] = json.dumps(d[field])
    with _get_write_lock(conn):
        conn.execute(
            """INSERT OR REPLACE INTO fsm_state (
                feature, current, rigor, current_conversation,
                retry_count_by_key, iteration_by_stage, updated_at,
                conv_start_sha, convs_total, convs_done, build_baseline, extra
            ) VALUES (
                :feature, :current, :rigor, :current_conversation,
                :retry_count_by_key, :iteration_by_stage, :updated_at,
                :conv_start_sha, :convs_total, :convs_done, :build_baseline, :extra
            )""",
            {
                "feature": d.get("feature"),
                "current": d.get("current"),
                "rigor": d.get("rigor"),
                "current_conversation": d.get("current_conversation"),
                "retry_count_by_key": d.get("retry_count_by_key"),
                "iteration_by_stage": d.get("iteration_by_stage"),
                "updated_at": d.get("updated_at", ""),
                "conv_start_sha": d.get("conv_start_sha"),
                "convs_total": d.get("convs_total"),
                "convs_done": d.get("convs_done"),
                "build_baseline": d.get("build_baseline"),
                "extra": d.get("extra"),
            },
        )
        conn.commit()


def read_state(conn: sqlite3.Connection, feature: str) -> dict | None:
    """Return the fsm_state row for *feature* as a dict, or None."""
    row = conn.execute(
        "SELECT * FROM fsm_state WHERE feature=?", (feature,)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    for field in _FSM_STATE_JSON_FIELDS:
        if d.get(field) is not None:
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


# ---------------------------------------------------------------------------
# runner_state helpers
# ---------------------------------------------------------------------------

_RUNNER_STATE_JSON_FIELDS = ("autonomy", "pending_menu", "open_session")


def write_runner_state(conn: sqlite3.Connection, feature: str, runner_dict: dict) -> None:
    """Upsert *runner_dict* into runner_state."""
    d = dict(runner_dict)
    d["feature"] = feature
    for field in _RUNNER_STATE_JSON_FIELDS:
        if field in d and not isinstance(d[field], str) and d[field] is not None:
            d[field] = json.dumps(d[field])
    with _get_write_lock(conn):
        conn.execute(
            """INSERT OR REPLACE INTO runner_state (
                feature, topic, flow, project_root, model, timeout, run_id,
                status, current_state, current_adapter, iterations, max_iterations,
                cost_usd_so_far, max_cost_usd, autonomy, pending_menu,
                error_kind, open_session, updated_at
            ) VALUES (
                :feature, :topic, :flow, :project_root, :model, :timeout, :run_id,
                :status, :current_state, :current_adapter, :iterations, :max_iterations,
                :cost_usd_so_far, :max_cost_usd, :autonomy, :pending_menu,
                :error_kind, :open_session, :updated_at
            )""",
            {
                "feature": d.get("feature"),
                "topic": d.get("topic"),
                "flow": d.get("flow"),
                "project_root": d.get("project_root"),
                "model": d.get("model"),
                "timeout": d.get("timeout"),
                "run_id": d.get("run_id"),
                "status": d.get("status", "idle"),
                "current_state": d.get("current_state", ""),
                "current_adapter": d.get("current_adapter"),
                "iterations": d.get("iterations", 0),
                "max_iterations": d.get("max_iterations"),
                "cost_usd_so_far": d.get("cost_usd_so_far", 0.0),
                "max_cost_usd": d.get("max_cost_usd"),
                "autonomy": d.get("autonomy", "{}"),
                "pending_menu": d.get("pending_menu"),
                "error_kind": d.get("error_kind"),
                "open_session": d.get("open_session"),
                "updated_at": d.get("updated_at"),
            },
        )
        conn.commit()


def read_runner_state(conn: sqlite3.Connection, feature: str) -> dict | None:
    """Return the runner_state row for *feature* as a dict, or None."""
    row = conn.execute(
        "SELECT * FROM runner_state WHERE feature=?", (feature,)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    for field in _RUNNER_STATE_JSON_FIELDS:
        if d.get(field) is not None:
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def mark_stale_runners(conn: sqlite3.Connection) -> int:
    """Set status='error' for all runner_state rows currently status='running'.

    Uses BEGIN IMMEDIATE to prevent a race between read and write.
    Returns the number of rows updated.
    """
    with _get_write_lock(conn):
        conn.execute("BEGIN IMMEDIATE")
        cur = conn.execute(
            "UPDATE runner_state SET status='error' WHERE status='running'"
        )
        conn.commit()
        return cur.rowcount
