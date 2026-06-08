"""Query helpers for the run_history table."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


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
) -> None:
    """Insert or update a run_history row."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO run_history "
            "(project_root, feature, run_id, status, started_at, finished_at, "
            " stage_count, total_tokens, cost_usd, adapter) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(run_id) DO UPDATE SET "
            "  status=excluded.status, "
            "  finished_at=excluded.finished_at, "
            "  stage_count=excluded.stage_count, "
            "  total_tokens=excluded.total_tokens, "
            "  cost_usd=excluded.cost_usd, "
            "  adapter=excluded.adapter",
            (
                project_root, feature, run_id, status,
                started_at or now, finished_at,
                stage_count, total_tokens, cost_usd, adapter,
            ),
        )
        conn.commit()


def read_run_history(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> list[dict]:
    """Return all runs for project_root/feature, newest first."""
    rows = conn.execute(
        "SELECT * FROM run_history WHERE project_root=? AND feature=? ORDER BY id DESC",
        (project_root, feature),
    ).fetchall()
    return [dict(r) for r in rows]
