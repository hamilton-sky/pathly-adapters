"""Schema migrations for pathly_orchestrator SQLite database."""
from __future__ import annotations

import sqlite3


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
""")
    conn.commit()
