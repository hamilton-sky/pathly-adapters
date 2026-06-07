"""Query helpers for the skill_definitions table."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def upsert_skill_definition(
    conn: sqlite3.Connection,
    project_root,
    skill: str,
    filename: str,
    natural_language: str,
    content: str,
) -> int:
    """Upsert a skill definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO skill_definitions "
            "(project_root, skill, filename, natural_language, content, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_root,
                skill,
                filename,
                natural_language,
                content,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_skill_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return skill definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM skill_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM skill_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]
