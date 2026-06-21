"""Query helpers for the feedback_items table."""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock


def write_feedback_item(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    filename: str,
    content: str | None,
) -> None:
    """Record an open feedback file. INSERT OR IGNORE — does not overwrite existing rows."""
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR IGNORE INTO feedback_items "
            "(project_root, feature, filename, content, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (project_root, feature, filename, content),
        )
        conn.commit()


def read_feedback_items(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
) -> list[dict]:
    """Return all unresolved feedback items for this feature, oldest first."""
    rows = conn.execute(
        "SELECT filename, content, created_at FROM feedback_items "
        "WHERE project_root=? AND feature=? AND resolved_at IS NULL "
        "ORDER BY created_at ASC",
        (project_root, feature),
    ).fetchall()
    return [{"filename": r[0], "content": r[1], "created_at": r[2]} for r in rows]


def resolve_feedback_item(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    filename: str,
) -> None:
    """Mark a feedback item as resolved (set resolved_at = now)."""
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE feedback_items SET resolved_at=datetime('now') "
            "WHERE project_root=? AND feature=? AND filename=? AND resolved_at IS NULL",
            (project_root, feature, filename),
        )
        conn.commit()
