"""Schema migrations for pathly_orchestrator SQLite database."""

from __future__ import annotations

import sqlite3
import uuid


def _run_migrations(conn: sqlite3.Connection, vec_available: bool = False) -> None:
    """Idempotent schema creation for all 14 tables + schema_version."""
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

CREATE TABLE IF NOT EXISTS stage_configs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    stage        TEXT NOT NULL,
    agent        TEXT,
    adapter      TEXT,
    skill        TEXT,
    updated_at   TEXT NOT NULL,
    UNIQUE(project_root, feature, stage)
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

-- Per-project (or global, project_root IS NULL) fragment-composition OVERRIDES.
-- The packaged composition.yaml is the version-controlled default/seed; edits from
-- the skill editor land here instead of rewriting the installed YAML file (which is
-- wiped on reinstall / dirties the repo). fragments_json is a JSON array of fragment
-- names, merged over the YAML defaults at read time by compose.load_effective_manifest.
CREATE TABLE IF NOT EXISTS skill_composition (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root   TEXT,
    skill_key      TEXT NOT NULL,
    fragments_json TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

INSERT OR IGNORE INTO schema_version VALUES (1, datetime('now'));

CREATE TABLE IF NOT EXISTS feedback_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    filename     TEXT NOT NULL,
    content      TEXT,
    created_at   TEXT NOT NULL,
    resolved_at  TEXT,
    UNIQUE(project_root, feature, filename)
);

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

CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_comp_global
    ON skill_composition(skill_key) WHERE project_root IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_skill_comp_proj
    ON skill_composition(skill_key, project_root) WHERE project_root IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_nodes_def_node
    ON flow_nodes(flow_def_id, node_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_flow_edges_def_src_tgt
    ON flow_edges(flow_def_id, source_node, target_node);

CREATE TABLE IF NOT EXISTS catalog_items (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    item_type    TEXT NOT NULL,
    name         TEXT NOT NULL,
    rel_path     TEXT,
    abs_path     TEXT,
    category     TEXT,
    description  TEXT,
    tags         TEXT,
    indexed_at   TEXT NOT NULL,
    UNIQUE(item_type, name)
);

CREATE TABLE IF NOT EXISTS run_history (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT NOT NULL,
    feature      TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    status       TEXT NOT NULL,
    started_at   TEXT,
    finished_at  TEXT,
    stage_count  INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    cost_usd     REAL DEFAULT 0.0,
    adapter      TEXT,
    UNIQUE(run_id)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS comms_messages (
    id                TEXT PRIMARY KEY,
    board             TEXT NOT NULL,
    scope             TEXT NOT NULL,
    from_agent        TEXT NOT NULL,
    to_agent          TEXT NOT NULL DEFAULT '*',
    type              TEXT NOT NULL,
    text              TEXT NOT NULL,
    options           TEXT,
    reply_to          TEXT,
    stage             TEXT,
    conv              INTEGER,
    ts                TEXT NOT NULL,
    read_by           TEXT DEFAULT '[]',
    acknowledged_by   TEXT DEFAULT '[]',
    status            TEXT DEFAULT 'pending',
    deleted_at        TEXT,
    promoted_to       TEXT,    -- reserved for future promotion feature
    promoted_from     TEXT,    -- reserved for future promotion feature
    original_scope    TEXT,    -- reserved for future promotion feature
    artifact_path     TEXT,
    artifact_type     TEXT,
    artifact_url      TEXT,
    task_status       TEXT,
    assigned_to_stage TEXT,
    assigned_to_agent TEXT,
    embedding_model   TEXT
);

-- One row per artifact produced on a board (many-per-task). board/scope are
-- derived through the message FK. version / last_edit_* / supersedes columns
-- exist now but stay at defaults — the editor-save + versioning hooks that
-- populate them are a deferred follow-up.
CREATE TABLE IF NOT EXISTS comms_artifacts (
    id            TEXT PRIMARY KEY,
    message_id    TEXT NOT NULL,
    path          TEXT NOT NULL,
    type          TEXT,
    title         TEXT,
    summary       TEXT,
    token_count   INTEGER,
    created_at    TEXT NOT NULL,
    created_by    TEXT,
    last_edit_at  TEXT,
    last_edit_by  TEXT,
    version       INTEGER DEFAULT 1,
    supersedes    TEXT
);

CREATE INDEX IF NOT EXISTS idx_comms_artifacts_msg  ON comms_artifacts(message_id);
CREATE INDEX IF NOT EXISTS idx_comms_artifacts_path ON comms_artifacts(path);

-- Section index: one row per heading-delimited section of a .md artifact.
-- anchor is the slug (§3.1 algorithm) or explicit pathly:anchor id.
-- line_start/line_end are 1-based inclusive; rebuilt on content change (§3.4).
-- summary is INDEX-tier (filled by inference service, Phase 4); stays NULL until then.
CREATE TABLE IF NOT EXISTS comms_artifact_sections (
    id            TEXT PRIMARY KEY,
    artifact_id   TEXT NOT NULL,
    anchor        TEXT NOT NULL,
    heading       TEXT,
    line_start    INTEGER NOT NULL,
    line_end      INTEGER NOT NULL,
    summary       TEXT,
    ordinal       INTEGER DEFAULT 0,
    UNIQUE(artifact_id, anchor)
);
CREATE INDEX IF NOT EXISTS idx_artifact_sections_artifact
    ON comms_artifact_sections(artifact_id);
""")
    conn.commit()
    if vec_available:
        try:
            conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS comms_embeddings USING vec0("
                "message_id TEXT PRIMARY KEY, "
                "embedding  FLOAT[384], "
                "chunk_index INTEGER DEFAULT 0, "
                "chunk_text  TEXT"
                ")"
            )
            conn.commit()
        except Exception:
            pass
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS comms_fts "
            "USING fts5(text, content=comms_messages, content_rowid=rowid, tokenize='porter ascii')"
        )
        conn.executescript("""
CREATE TRIGGER IF NOT EXISTS comms_fts_ai AFTER INSERT ON comms_messages BEGIN
  INSERT INTO comms_fts(rowid, text) VALUES (NEW.rowid, NEW.text);
END;
CREATE TRIGGER IF NOT EXISTS comms_fts_au AFTER UPDATE ON comms_messages BEGIN
  INSERT INTO comms_fts(comms_fts, rowid, text) VALUES ('delete', OLD.rowid, OLD.text);
  INSERT INTO comms_fts(rowid, text) VALUES (NEW.rowid, NEW.text);
END;
CREATE TRIGGER IF NOT EXISTS comms_fts_ad AFTER DELETE ON comms_messages BEGIN
  INSERT INTO comms_fts(comms_fts, rowid, text) VALUES ('delete', OLD.rowid, OLD.text);
END;
""")
        conn.commit()
    except Exception:
        pass
    _add_additive_migrations(conn)
    _backfill_comms_artifacts(conn)


def _backfill_comms_artifacts(conn: sqlite3.Connection) -> None:
    """One-time, idempotent back-fill of comms_artifacts from existing artifact
    messages.

    For every non-deleted ``type='artifact'`` message that has an
    ``artifact_path`` but no comms_artifacts row yet, insert one. token_count is
    left NULL (the DB layer never touches the filesystem — the modal computes
    size/tokens live, and post-time wiring fills it for new artifacts). Safe to
    run on every startup: the LEFT JOIN ... a.id IS NULL guard skips rows that
    already have an artifact. Positional row access so it works regardless of
    row_factory.
    """
    try:
        rows = conn.execute(
            "SELECT m.id, m.from_agent, m.text, m.artifact_path, m.artifact_type, m.ts "
            "FROM comms_messages m "
            "LEFT JOIN comms_artifacts a ON a.message_id = m.id "
            "WHERE m.type='artifact' AND m.artifact_path IS NOT NULL "
            "AND m.deleted_at IS NULL AND a.id IS NULL"
        ).fetchall()
    except sqlite3.OperationalError:
        return
    for r in rows:
        mid, from_agent, text, path, atype, ts = r[0], r[1], r[2], r[3], r[4], r[5]
        title = path.replace("\\", "/").rsplit("/", 1)[-1] if path else None
        conn.execute(
            "INSERT INTO comms_artifacts "
            "(id, message_id, path, type, title, summary, token_count, created_at, created_by, version) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, 1)",
            (str(uuid.uuid4()), mid, path, atype, title, text, ts, from_agent),
        )
    conn.commit()


def _add_additive_migrations(conn: sqlite3.Connection) -> None:
    """ALTER TABLE migrations — safe to re-run; skips columns that already exist."""
    for table, col, ctype in [
        ("catalog_items", "content", "TEXT"),
        ("flow_definitions", "file_path", "TEXT"),
        # Phase 4 (provider-agnostic-telemetry): cost confidence + provider tracking
        ("agent_invocations", "cost_source", "TEXT DEFAULT 'unpriced'"),
        ("agent_invocations", "provider", "TEXT"),
        ("agent_invocations", "cache_read_tokens", "INTEGER DEFAULT 0"),
        ("agent_invocations", "cache_write_tokens", "INTEGER DEFAULT 0"),
        ("run_history", "cost_source", "TEXT DEFAULT 'unpriced'"),
        ("run_history", "provider", "TEXT"),
        # flow-nodes-edges-migration: normalized storage for flow graph
        ("flow_nodes", "agent", "TEXT"),
        ("flow_nodes", "role", "TEXT"),
        ("flow_nodes", "adapter", "TEXT"),
        ("flow_nodes", "skill", "TEXT"),
        ("flow_nodes", "is_terminal", "INTEGER DEFAULT 0"),
        ("flow_nodes", "position", "INTEGER DEFAULT 0"),
        ("flow_edges", "config_json", "TEXT"),
        ("flow_edges", "ordinal", "INTEGER DEFAULT 0"),
        ("flow_definitions", "config_json", "TEXT"),
        # Phase 1.4a (comms-board): supersede stale decisions
        ("comms_messages", "superseded_by", "TEXT"),
        # Phase 14 (comms-board-skills): DAG task decomposition
        ("comms_messages", "depends_on", "TEXT"),
        # P2 scheduler: lane partition + claim/fail lifecycle
        ("comms_messages", "lane", "TEXT"),
        ("comms_messages", "claimed_at", "TEXT"),
        ("comms_messages", "claimed_by", "TEXT"),
        ("comms_messages", "failed_at", "TEXT"),
        ("comms_messages", "fail_reason", "TEXT"),
        ("comms_messages", "attempts", "INTEGER DEFAULT 0"),
        # board-context-pull (Solution B): task completion timestamp. Paired with
        # claimed_at, it yields per-task claim→complete duration for the Goals view.
        ("comms_messages", "completed_at", "TEXT"),
        # comms-board-dag-serial: Board -> Goals -> per-goal task-DAG.
        # goal_id ties a task to its goal; executor ('single'|'loop'|'team') is
        # set on the goal message. A goal is type='goal' (existing type column).
        ("comms_messages", "goal_id", "TEXT"),
        ("comms_messages", "executor", "TEXT"),
        # comms-board context-retrieval: advisory artifact links carried on the task.
        # Phase 2 — SHAPE guard only; resolve-against-index gate lands in Phase 3.
        ("comms_messages", "context_refs", "TEXT"),
        # Phase 3 — staleness fingerprints for the section index (§3.4).
        # indexed_mtime: st_mtime at last index (cheap gate, one stat).
        # indexed_hash: sha256 of full file content at last index (content-change gate).
        # indexed_structure_key: order-independent set of heading slugs (structural-change gate).
        ("comms_artifacts", "indexed_mtime", "REAL"),
        ("comms_artifacts", "indexed_hash", "TEXT"),
        ("comms_artifacts", "indexed_structure_key", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
