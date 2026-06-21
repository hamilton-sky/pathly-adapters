"""Query helpers for the skill_overrides table."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


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
