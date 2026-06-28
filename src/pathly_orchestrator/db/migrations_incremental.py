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
