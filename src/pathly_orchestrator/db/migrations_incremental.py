"""Additive (ALTER TABLE) migrations and one-time backfills."""

from __future__ import annotations

import sqlite3
import uuid


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
        # telemetry-three-tier: board tier each invocation/span ran under
        # (feature|project|global). A TAG for aggregate-on-read roll-up, NOT a
        # separate counter row — project/global totals are GROUP BYs over this.
        ("agent_invocations", "scope_tier", "TEXT DEFAULT 'feature'"),
        ("otel_spans", "scope_tier", "TEXT DEFAULT 'feature'"),
        # telemetry-reconciliation: the fsm_events.seq of the AGENT_DONE this
        # invocation projects from. NULL = a row NOT derived from the event stream
        # (editor/chat one-shots posted via /db/invocation, which have no event).
        # The projector keys rows by (project_root, feature, source_seq) so the
        # backfill + live hook stay idempotent and never double-count.
        ("agent_invocations", "source_seq", "INTEGER"),
        # recent-category: run TYPE ('flow'|'single'|'loop') — scope_tier (the board tier)
        # can't express it, so the Monitor's RECENT list mis-bucketed board/single runs as
        # 'flow'. Stamped into the AGENT_DONE event (<run_category>) so it survives the backfill.
        ("agent_invocations", "category", "TEXT"),
        # run-identity: board scope (the parent feature/project a run belongs to) stamped
        # at spawn into the event row, so consumers stop re-deriving it from storage
        # location. NULL = legacy row; every reader keeps its current heuristic for NULL.
        ("fsm_events", "board_scope", "TEXT"),
        # run-identity: the same spawn-issued board scope on the projected invocation row
        # (copied from the AGENT_DONE payload; a BILLING_UPDATE fills it only when the
        # anchor lacks one) and on the run_history identity map (run_id → project_root,
        # feature slug, board_scope). NULL = legacy — never guessed, never backfilled.
        ("agent_invocations", "board_scope", "TEXT"),
        ("run_history", "board_scope", "TEXT"),
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
        # flow-phase-inspector (#5): per-stage layer-3 ability ids + excluded section
        # headings, each a JSON list. The SELECTION (not frozen prompt text) — fsm_compose
        # composes fresh at spawn and applies it, so an upstream skill edit never stale-seeds.
        ("stage_configs", "ability_ids", "TEXT"),
        ("stage_configs", "excluded_sections", "TEXT"),
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
        # cross-feature file-claims: JSON list of files/dir-globs a task will touch.
        # Gates concurrent feature builds — disjoint sets run in parallel, overlaps
        # serialize; NULL/absent = undeclared (treated as "touches everything").
        ("comms_messages", "files", "TEXT"),
        # T5 goal-slug: stable filesystem slug for goal messages.
        ("comms_messages", "slug", "TEXT"),
        # question-answer-persistence: the chosen option id on an answered question row.
        # Without it the option id never round-trips, so the board's 5s fallback poll
        # reloaded the question with no selection and reverted the highlight.
        ("comms_messages", "answer_option", "TEXT"),
        # Phase 3 — staleness fingerprints for the section index (§3.4).
        # indexed_mtime: st_mtime at last index (cheap gate, one stat).
        # indexed_hash: sha256 of full file content at last index (content-change gate).
        # indexed_structure_key: order-independent set of heading slugs (structural-change gate).
        ("comms_artifacts", "indexed_mtime", "REAL"),
        ("comms_artifacts", "indexed_hash", "TEXT"),
        ("comms_artifacts", "indexed_structure_key", "TEXT"),
        # unified-ai-routing (Conv 3): per-artifact AI target for client-side
        # summarization. JSON-encoded AiSelection {"type":"model"|"engine","id":...}.
        # Nullable → the artifact falls back to the app-default selection.
        ("comms_artifacts", "summary_selection", "TEXT"),
        # summary-style: per-artifact summary DEPTH ('gist'|'topic-map'|'detailed').
        # Selects which development/summarize* skill the client composes. Nullable →
        # falls back to the default ('topic-map').
        ("comms_artifacts", "summary_style", "TEXT"),
        # summary-note: per-artifact free-text "special request" appended to the summary
        # prompt (e.g. "focus on security"). Nullable → no extra instruction.
        ("comms_artifacts", "summary_note", "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype}")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
    # Partial unique index on slug (only for non-NULL values) — allows many NULL slugs
    # while preventing duplicate slugs on distinct goal messages.
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_comms_messages_slug "
            "ON comms_messages(slug) WHERE slug IS NOT NULL"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
    # telemetry-reconciliation: one invocation row per projected AGENT_DONE.
    # Partial unique index (source_seq NOT NULL) — event-less editor/chat rows keep
    # NULL source_seq and are unconstrained; projected rows upsert by this key.
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_agent_invocations_source "
            "ON agent_invocations(project_root, feature, source_seq) "
            "WHERE source_seq IS NOT NULL"
        )
        conn.commit()
    except sqlite3.OperationalError:
        pass
