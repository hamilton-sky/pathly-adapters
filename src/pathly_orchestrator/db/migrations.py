"""Schema migrations for pathly_orchestrator SQLite database."""

from __future__ import annotations

import sqlite3

from pathly_orchestrator.db.migrations_incremental import (
    _add_additive_migrations,
    _backfill_comms_artifacts,
)


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
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root      TEXT NOT NULL,
    feature           TEXT NOT NULL,
    stage             TEXT NOT NULL,
    agent             TEXT,
    adapter           TEXT,
    skill             TEXT,
    ability_ids       TEXT,
    excluded_sections TEXT,
    updated_at        TEXT NOT NULL,
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

-- unified-control-plane P0: per-spawn Complete Run Record — the prompt sent to the CLI,
-- the injected board context, stdin, and the full (untruncated) PTY stdout tail. One row
-- per spawn (run_id is effectively unique per spawn; retries mint -q{n}/-fb{n} variants).
-- A debug/display SINK — billing stays authoritative in agent_invocations. Not UNIQUE(run_id)
-- so the write path stays INSERT + WHERE-run_id UPDATE; a stray dup degrades to "newest wins".
CREATE TABLE IF NOT EXISTS run_log (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id                 TEXT NOT NULL,
    stage                  TEXT,
    prompt_sent            TEXT,
    board_context_injected TEXT,
    stdin                  TEXT,
    stdout                 TEXT,
    ts                     TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_run_log_run_id ON run_log(run_id);

CREATE TABLE IF NOT EXISTS app_settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- The ONE library behind every prompt dropdown + the layer-3 ability packs.
--   kind='preset'  → single-select alternatives (analyze/diagram/eval/system dropdowns)
--   kind='ability' → additive, stackable modifiers (domain/approach packs)
-- category buckets within a kind. skill_ref is the optional compose bridge. source is
-- 'builtin' (seeded) or 'user' (added in the UI). project_root IS NULL is a GLOBAL row;
-- a project row overrides a global one on the same (kind, category, name).
CREATE TABLE IF NOT EXISTS prompt_library (
    id           TEXT PRIMARY KEY,
    project_root TEXT,
    kind         TEXT NOT NULL,
    category     TEXT NOT NULL,
    name         TEXT NOT NULL,
    label        TEXT NOT NULL,
    hint         TEXT,
    body         TEXT NOT NULL,
    skill_ref    TEXT,
    source       TEXT NOT NULL DEFAULT 'user',
    sort_order   INTEGER DEFAULT 0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_lib_global
    ON prompt_library(kind, category, name) WHERE project_root IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_prompt_lib_proj
    ON prompt_library(kind, category, name, project_root) WHERE project_root IS NOT NULL;

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
-- summary is filled CLIENT-side via the AI Router (unified-ai-routing); NULL until summarized.
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

-- Child-chunk embeddings: per-bullet (topic-map) / per-section (detailed) vectors for an
-- artifact summary, so a query matching ONE subtopic still retrieves the artifact. A REGULAR
-- table (not vec0): vec_distance_cosine() works over the BLOB just like the existing brute-force
-- scan, and a normal table supports DELETE-by-message + multiple rows per message (vec0's
-- message_id PRIMARY KEY does not). The whole-summary "parent" vector stays in comms_embeddings.
CREATE TABLE IF NOT EXISTS comms_chunk_embeddings (
    chunk_id    TEXT PRIMARY KEY,
    message_id  TEXT NOT NULL,
    embedding   BLOB,
    chunk_text  TEXT
);
CREATE INDEX IF NOT EXISTS idx_chunk_emb_message
    ON comms_chunk_embeddings(message_id);
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
    # telemetry-reconciliation: rebuild the event-backed slice of agent_invocations
    # from the fsm_events AGENT_DONE/BILLING_UPDATE stream. Idempotent; skips the
    # event-less editor/chat rows. Best-effort — a telemetry backfill must never
    # block DB startup.
    try:
        from pathly_orchestrator.db.queries.invocation_projection import (
            backfill_invocations_from_events,
        )

        backfill_invocations_from_events(conn)
    except Exception:
        pass
    # board-disk-mirror P0: idempotent startup pass that exports every known project's
    # comms boards to BOARD.json on disk (pure export; never mutates the DB). Same
    # lazy-import + best-effort pattern as the invocation-projection backfill above —
    # a mirror-write failure must never block DB startup.
    try:
        from pathly_orchestrator.board_mirror import backfill_board_mirrors

        backfill_board_mirrors(conn)
    except Exception:
        pass
    # state-one-authority: idempotent startup pass that exports each feature's fsm_events
    # log to EVENTS.jsonl on disk (pure DB->disk export; never mutates the DB). Same
    # lazy-import + best-effort pattern as the board-mirror backfill above — a mirror-write
    # failure must never block DB startup.
    try:
        from pathly_orchestrator.event_mirror import backfill_event_mirrors

        backfill_event_mirrors(conn)
    except Exception:
        pass
