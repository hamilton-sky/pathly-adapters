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
    file_path: str = "",
) -> int:
    """Upsert a flow definition. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO flow_definitions "
            "(project_root, name, version, flow_yaml, file_path, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_root,
                name,
                version,
                flow_yaml,
                file_path,
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


def read_flow_by_name(conn: sqlite3.Connection, name: str, project_root=None) -> dict | None:
    """Return a single flow definition by name, or None if not found."""
    if project_root is not None:
        row = conn.execute(
            "SELECT * FROM flow_definitions WHERE name=? AND project_root=?",
            (name, project_root)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM flow_definitions WHERE name=? AND project_root IS NULL",
            (name,)
        ).fetchone()
        if row is None:
            # Fallback: any flow with this name
            row = conn.execute(
                "SELECT * FROM flow_definitions WHERE name=? ORDER BY project_root IS NULL DESC LIMIT 1",
                (name,)
            ).fetchone()
    return dict(row) if row else None


def _refresh_flows(conn: sqlite3.Connection) -> None:
    """Walk pathly_data/core/flows and upsert each .flow.yaml into flow_definitions.
    Called on every server start to keep DB in sync with filesystem.
    """
    from .catalog_items import _find_data_root
    data_root = _find_data_root()
    if data_root is None:
        return
    flows_dir = data_root / "core" / "flows"
    if not flows_dir.exists():
        return
    for f in sorted(flows_dir.glob("*.flow.yaml")):
        # team.flow.yaml -> team
        name = f.stem  # e.g. team.flow
        if name.endswith(".flow"):
            name = name[:-5]
        try:
            flow_yaml = f.read_text(encoding="utf-8")
            upsert_flow_definition(
                conn,
                project_root=None,
                name=name,
                version="",
                flow_yaml=flow_yaml,
                file_path=str(f).replace("\\", "/"),
            )
        except Exception:
            pass
