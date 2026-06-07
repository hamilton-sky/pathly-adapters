"""Query helpers for the flow_definitions table."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def upsert_flow_definition(
    conn: sqlite3.Connection,
    project_root,
    name: str,
    version: str,
    flow_yaml: str,
) -> int:
    """Upsert a flow definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO flow_definitions "
            "(project_root, name, version, flow_yaml, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                project_root,
                name,
                version,
                flow_yaml,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_flow_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return flow definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM flow_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM flow_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]
