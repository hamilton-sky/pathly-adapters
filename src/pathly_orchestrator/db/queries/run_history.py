"""Query helpers for the run_history table."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock
from .fsm_events import _norm


def upsert_run(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    run_id: str,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    stage_count: int = 0,
    total_tokens: int = 0,
    cost_usd: float = 0.0,
    adapter: str | None = None,
    board_scope: str | None = None,
) -> None:
    """Insert or update a run_history row (the run-identity map: run_id →
    project_root, feature SLUG, board_scope).

    Identity fields are ISSUE-ONCE: ``board_scope`` is COALESCEd existing-wins (a
    later writer fills a NULL but never overwrites the spawn-issued value), and
    ``adapter`` keeps its last real value when a later writer passes None (the
    registry finish-upsert used to NULL it out). ``project_root`` is normalized like
    fsm_events (forward slashes) so a Windows backslash caller never splits the key.
    """
    project_root = _norm(project_root)
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO run_history "
            "(project_root, feature, run_id, status, started_at, finished_at, "
            " stage_count, total_tokens, cost_usd, adapter, board_scope) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(run_id) DO UPDATE SET "
            "  status=excluded.status, "
            "  finished_at=excluded.finished_at, "
            "  stage_count=excluded.stage_count, "
            "  total_tokens=excluded.total_tokens, "
            "  cost_usd=excluded.cost_usd, "
            "  adapter=COALESCE(excluded.adapter, adapter), "
            "  board_scope=COALESCE(board_scope, excluded.board_scope)",
            (
                project_root,
                feature,
                run_id,
                status,
                started_at or now,
                finished_at,
                stage_count,
                total_tokens,
                cost_usd,
                adapter,
                board_scope,
            ),
        )
        conn.commit()


# Legacy-row normalization shim (run-identity): rows written before the slug keying
# fix hold a FULL topic path (features/<f>/goals/<slug>, or a project-root path) in
# `feature`. They are never rewritten — instead the readers below also match rows
# whose path BASENAME equals the queried slug. New rows always store the slug.
_SLUG_MATCH = "(feature=? OR feature LIKE '%/' || ?)"


def read_run_history(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> list[dict]:
    """Return all runs for project_root/feature (slug or legacy path-suffix), newest first."""
    rows = conn.execute(
        "SELECT * FROM run_history "  # nosec B608 - _SLUG_MATCH is a module constant; values are bound
        f"WHERE project_root=? AND {_SLUG_MATCH} ORDER BY id DESC",
        (_norm(project_root), feature, feature),
    ).fetchall()
    return [dict(r) for r in rows]


def latest_project_root_for_feature(
    conn: sqlite3.Connection, feature: str
) -> str | None:
    """The most-recent project_root that ran *feature*. This is the board disk-mirror's
    ★ resolution for a feature board — its comms scope is the feature id alone, with no
    root, so the live mirror writer reuses run_history's (project_root, feature) mapping
    to place BOARD.json. No new column needed. None if the feature has no run history.
    Matches legacy full-path rows by basename (normalization shim above).
    """
    row = conn.execute(
        "SELECT project_root FROM run_history "  # nosec B608 - _SLUG_MATCH is a module constant; values are bound
        f"WHERE {_SLUG_MATCH} ORDER BY id DESC LIMIT 1",
        (feature, feature),
    ).fetchone()
    return row["project_root"] if row else None
