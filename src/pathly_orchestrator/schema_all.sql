-- ================================================================
-- Pathly SQLite — Complete Schema
-- ================================================================
-- ONE DATABASE:  ~/.pathly/pathly.db
--
-- All structured data lives here.
-- The selected project folder is only a workspace for artifact
-- files (.md files) that agents read and write.
--
-- ── Global config (no project_root — reusable across all projects)
--    4.  flow_definitions
--    5.  flow_nodes
--    6.  flow_edges
--
-- ── Runtime data (project_root + feature identify each row)
--    1.  fsm_events
--    2.  fsm_state
--    3.  runner_state
--    7.  agent_invocations
--    8.  otel_spans
--    9.  skill_overrides
--    10. stage_artifacts
--
-- ── Scoped config (project_root=NULL → global, non-NULL → local override)
--    11. skill_definitions
--    12. agent_definitions
--
-- Tables 1-3: EXISTING — need project_root column added
-- Tables 4-6: NEW — flow definitions (replaces YAML as source of truth)
-- Tables 7-10: NEW — runtime telemetry + artifacts
-- Tables 11-12: NEW — skill and agent config
-- ================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;


-- ────────────────────────────────────────────────────────
-- 1. fsm_events  (EXISTING — add project_root)
--    Append-only log — every FSM event ever fired.
--    project_root + feature + seq uniquely identify an event.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fsm_events (
    seq              INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root     TEXT    NOT NULL,   -- absolute path to project folder
    feature          TEXT    NOT NULL,
    type             TEXT    NOT NULL,   -- AGENT_START | AGENT_DONE | PHASE_START
                                         -- PHASE_DONE | STATE_TRANSITION | RUNNER_REROUTE
    ts               TEXT    NOT NULL,   -- ISO-8601
    schema_version   INTEGER DEFAULT 1,
    payload          TEXT    NOT NULL    -- full JSON blob
);
CREATE INDEX IF NOT EXISTS idx_events_project ON fsm_events(project_root, feature, seq);
CREATE INDEX IF NOT EXISTS idx_events_type    ON fsm_events(project_root, feature, type);


-- ────────────────────────────────────────────────────────
-- 2. fsm_state  (EXISTING — change PK, add project_root)
--    Current FSM position for each feature in each project.
--    PK is (project_root, feature) — same feature name can
--    exist in different project folders without collision.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fsm_state (
    project_root         TEXT NOT NULL,  -- absolute path to project folder
    feature              TEXT NOT NULL,
    current              TEXT NOT NULL,
    rigor                TEXT,
    current_conversation INTEGER,
    retry_count_by_key   TEXT,           -- JSON
    iteration_by_stage   TEXT,           -- JSON
    updated_at           TEXT NOT NULL,
    conv_start_sha       TEXT,
    convs_total          INTEGER,
    convs_done           INTEGER,
    build_baseline       TEXT,           -- JSON
    extra                TEXT,           -- JSON extension bag
    PRIMARY KEY (project_root, feature)
);
CREATE INDEX IF NOT EXISTS idx_fsm_state_project ON fsm_state(project_root);


-- ────────────────────────────────────────────────────────
-- 3. runner_state  (EXISTING — change PK, add project_root)
--    Live runner execution state.
--    PK is (project_root, feature).
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS runner_state (
    project_root     TEXT NOT NULL,    -- absolute path to project folder
    feature          TEXT NOT NULL,
    topic            TEXT,
    flow             TEXT,             -- 'team' | 'standard' | 'nano' → FK to flow_definitions
    model            TEXT,
    timeout          INTEGER,
    run_id           TEXT,
    status           TEXT DEFAULT 'idle',  -- idle | running | paused | done | error | aborted
    current_state    TEXT DEFAULT '',
    current_adapter  TEXT,             -- claude | codex | copilot | antigravity
    iterations       INTEGER DEFAULT 0,
    max_iterations   INTEGER,
    cost_usd_so_far  REAL    DEFAULT 0.0,
    max_cost_usd     REAL,
    autonomy         TEXT    DEFAULT '{}', -- JSON
    pending_menu     TEXT,                 -- JSON
    error_kind       TEXT,
    open_session     TEXT,                 -- JSON
    updated_at       TEXT,
    PRIMARY KEY (project_root, feature)
);
CREATE INDEX IF NOT EXISTS idx_runner_project ON runner_state(project_root);


-- ────────────────────────────────────────────────────────
-- 4. flow_definitions  (NEW — global, no project_root)
--    Replaces YAML files as the source of truth for flows.
--    YAML becomes import/export only once this ships.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS flow_definitions (
    id           TEXT    PRIMARY KEY,    -- 'team' | 'standard' | 'nano' | custom slug
    name         TEXT    NOT NULL,
    description  TEXT,
    rigor        TEXT,                   -- nano | lite | standard | strict
    version      INTEGER DEFAULT 1,
    raw_yaml     TEXT,                   -- original YAML kept for export + git diff
    created_at   TEXT    NOT NULL,
    updated_at   TEXT    NOT NULL
);


-- ────────────────────────────────────────────────────────
-- 5. flow_nodes  (NEW — global, no project_root)
--    One row per stage in a flow.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS flow_nodes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id      TEXT    NOT NULL REFERENCES flow_definitions(id) ON DELETE CASCADE,
    name         TEXT    NOT NULL,       -- 'BUILD' | 'REVIEW' | custom
    agent_role   TEXT,                   -- builder | reviewer | tester | ...
    skill_name   TEXT,                   -- 'pathly-build.md' (default for this node)
    adapter      TEXT    DEFAULT 'claude', -- claude | codex | copilot | antigravity
    description  TEXT,
    pos_x        REAL    DEFAULT 0,      -- canvas x position
    pos_y        REAL    DEFAULT 0,      -- canvas y position
    UNIQUE(flow_id, name)
);


-- ────────────────────────────────────────────────────────
-- 6. flow_edges  (NEW — global, no project_root)
--    Transitions between stages.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS flow_edges (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_id      TEXT    NOT NULL REFERENCES flow_definitions(id) ON DELETE CASCADE,
    from_node    TEXT    NOT NULL,
    to_node      TEXT    NOT NULL,
    condition    TEXT,                   -- 'PASS' | 'FAIL' | 'BLOCK' | NULL = unconditional
    label        TEXT,
    UNIQUE(flow_id, from_node, to_node, condition)
);


-- ────────────────────────────────────────────────────────
-- 7. agent_invocations  (NEW — project_root scoped)
--    One row per agent run.
--    Drives: monitoring charts, run history, cost breakdown.
--    Written by the runner on each AGENT_DONE event.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_invocations (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root     TEXT    NOT NULL,
    feature          TEXT    NOT NULL,
    run_id           TEXT,
    stage            TEXT    NOT NULL,   -- BUILD | REVIEW | TEST | ...
    conv_id          TEXT,               -- bld-01 | bld-02 within the stage
    agent_role       TEXT    NOT NULL,   -- builder | reviewer | tester | ...
    model            TEXT,
    input_tokens     INTEGER DEFAULT 0,
    output_tokens    INTEGER DEFAULT 0,
    tool_uses        INTEGER DEFAULT 0,
    cost_usd         REAL    DEFAULT 0.0,
    wall_seconds     REAL,
    result           TEXT,               -- PASS | FAIL | BLOCK | ERROR
    summary          TEXT,               -- AGENT_DONE.summary (not truncated)
    session_id       TEXT,
    trace_id         TEXT,               -- → otel_spans.trace_id
    span_id          TEXT,               -- → otel_spans.span_id
    started_at       TEXT    NOT NULL,
    finished_at      TEXT
);
CREATE INDEX IF NOT EXISTS idx_inv_project ON agent_invocations(project_root, feature);
CREATE INDEX IF NOT EXISTS idx_inv_stage   ON agent_invocations(project_root, feature, stage);
CREATE INDEX IF NOT EXISTS idx_inv_trace   ON agent_invocations(trace_id);


-- ────────────────────────────────────────────────────────
-- 8. otel_spans  (NEW — project_root scoped)
--    Local cache of OTLP spans.
--    Written by otel_export.py alongside the HTTP post to collector.
--    Trace UI works even with no external collector configured.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS otel_spans (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    trace_id         TEXT    NOT NULL,
    span_id          TEXT    NOT NULL,
    parent_span_id   TEXT,
    project_root     TEXT    NOT NULL,
    feature          TEXT    NOT NULL,
    name             TEXT    NOT NULL,
    start_time_ns    INTEGER NOT NULL,
    end_time_ns      INTEGER,
    status_code      TEXT    DEFAULT 'UNSET',  -- OK | ERROR | UNSET
    status_message   TEXT,
    attributes       TEXT    DEFAULT '{}',     -- JSON flat map of OTLP attributes
    UNIQUE(trace_id, span_id)
);
CREATE INDEX IF NOT EXISTS idx_spans_trace   ON otel_spans(trace_id);
CREATE INDEX IF NOT EXISTS idx_spans_project ON otel_spans(project_root, feature);


-- ────────────────────────────────────────────────────────
-- 9. skill_overrides  (NEW — project_root scoped)
--    Runtime skill swap: user picks a different skill for
--    a stage before it executes.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skill_overrides (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root TEXT    NOT NULL,
    feature      TEXT    NOT NULL,
    run_id       TEXT    NOT NULL,
    stage        TEXT    NOT NULL,       -- 'REVIEW'
    skill_name   TEXT    NOT NULL,       -- 'pathly-review-strict.md'
    selected_at  TEXT    NOT NULL,
    status       TEXT    DEFAULT 'pending',  -- pending | applied | skipped
    UNIQUE(project_root, feature, run_id, stage)
);
CREATE INDEX IF NOT EXISTS idx_overrides_run ON skill_overrides(project_root, feature, run_id);


-- ────────────────────────────────────────────────────────
-- 10. stage_artifacts  (NEW — project_root scoped)
--     Mirrors the .md files agents write into the DB after
--     each stage completes.
--     DB Explorer shows content without opening files.
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS stage_artifacts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    project_root  TEXT    NOT NULL,
    feature       TEXT    NOT NULL,
    run_id        TEXT    NOT NULL,
    stage         TEXT    NOT NULL,
    artifact_type TEXT    NOT NULL,      -- REVIEW_FAILURES | TEST_FAILURES
                                         -- USER_STORIES | IMPLEMENTATION_PLAN
                                         -- CONVERSATION_PROMPTS | RETRO
    content       TEXT,
    file_path     TEXT,                  -- original path (traceability)
    created_at    TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_artifacts_project ON stage_artifacts(project_root, feature, run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_type    ON stage_artifacts(project_root, feature, artifact_type);


-- ────────────────────────────────────────────────────────
-- 11. skill_definitions  (NEW)
--     project_root = NULL  → global skill (available everywhere)
--     project_root = path  → local override (this project only)
--
--     Lookup order: local first → global fallback
--     SELECT ... WHERE file_name=?
--       AND (project_root=? OR project_root IS NULL)
--       ORDER BY project_root IS NULL   -- local wins (0 before 1)
--       LIMIT 1
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS skill_definitions (
    id                TEXT    NOT NULL,
    file_name         TEXT    NOT NULL,
    display_name      TEXT    NOT NULL,
    category          TEXT    NOT NULL,  -- build | review | test | plan | custom
    content           TEXT    NOT NULL,
    description       TEXT,
    compatible_stages TEXT    DEFAULT '[]',
    project_root      TEXT,              -- NULL = global, path = local override
    is_custom         INTEGER DEFAULT 0, -- 0 = built-in, 1 = user-created
    version           INTEGER DEFAULT 1,
    created_at        TEXT    NOT NULL,
    updated_at        TEXT    NOT NULL,
    PRIMARY KEY (id, COALESCE(project_root, ''))
);
CREATE INDEX IF NOT EXISTS idx_skills_filename  ON skill_definitions(file_name, project_root);
CREATE INDEX IF NOT EXISTS idx_skills_category  ON skill_definitions(category, project_root);


-- ────────────────────────────────────────────────────────
-- 12. agent_definitions  (NEW)
--     project_root = NULL  → global role (available everywhere)
--     project_root = path  → local override (this project only)
--
--     Use case: override model or instructions for one project
--     Lookup: same pattern as skill_definitions
-- ────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS agent_definitions (
    role          TEXT    NOT NULL,
    display_name  TEXT    NOT NULL,
    model         TEXT    NOT NULL,
    description   TEXT,
    instructions  TEXT,
    capabilities  TEXT    DEFAULT '[]',
    project_root  TEXT,              -- NULL = global, path = local override
    is_custom     INTEGER DEFAULT 0,
    created_at    TEXT    NOT NULL,
    updated_at    TEXT    NOT NULL,
    PRIMARY KEY (role, COALESCE(project_root, ''))
);
CREATE INDEX IF NOT EXISTS idx_agents_role ON agent_definitions(role, project_root);
