"""Query helpers for the agent_definitions table."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def upsert_agent_definition(
    conn: sqlite3.Connection,
    project_root,
    role: str,
    name: str,
    description: str,
    model: str,
    tools: list,
    can_spawn: list,
) -> int:
    """Upsert an agent definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO agent_definitions "
            "(project_root, role, name, description, model, tools_json, can_spawn_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root,
                role,
                name,
                description,
                model,
                json.dumps(tools),
                json.dumps(can_spawn),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_agent_definitions(conn: sqlite3.Connection, project_root=None) -> list[dict]:
    """Return agent definitions. If project_root given, filter by it; else global (NULL) only."""
    if project_root is not None:
        rows = conn.execute(
            "SELECT * FROM agent_definitions WHERE project_root=?", (project_root,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM agent_definitions WHERE project_root IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]
