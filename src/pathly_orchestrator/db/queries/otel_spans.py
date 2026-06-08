"""Query helpers for the otel_spans table."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def write_otel_span(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    name: str,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    attributes: str | None = None,
) -> int:
    """Insert an otel_spans row. Returns the new row id."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO otel_spans "
            "(project_root, feature, trace_id, span_id, parent_span_id, "
            " name, start_time, end_time, attributes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root, feature, trace_id, span_id, parent_span_id,
                name, start_time or now, end_time or now, attributes,
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_otel_spans(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> list[dict]:
    """Return all otel spans for project_root/feature, newest first."""
    rows = conn.execute(
        "SELECT * FROM otel_spans WHERE project_root=? AND feature=? ORDER BY id DESC",
        (project_root, feature),
    ).fetchall()
    return [dict(r) for r in rows]
