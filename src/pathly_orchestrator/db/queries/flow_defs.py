"""Flow definition lifecycle — upsert, read, and seed from pathly_data.

Graph decomposition/assembly helpers live in flow_graph_ops.py.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone

import yaml

from ..connection import _get_write_lock
from .flow_graph_ops import (  # noqa: F401
    _ASSEMBLED_FLOW_KEYS,
    _STRUCTURAL_FLOW_KEYS,
    _assemble_flow_dict,
    _assemble_from_parts,
    _decompose_flow_dict,
    read_flow_edges,
    read_flow_nodes,
    replace_flow_graph,
)

_log = logging.getLogger(__name__)


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
        flow_def_id = cur.lastrowid or 0
        conn.commit()

    try:
        flow_dict = yaml.safe_load(flow_yaml)
        if isinstance(flow_dict, dict):
            flow_level_cfg, nodes, edges = _decompose_flow_dict(flow_dict)
            replace_flow_graph(
                conn, flow_def_id, flow_level_cfg, nodes, edges, commit=True
            )
    except Exception:
        _log.warning(
            "upsert_flow_definition: decomposition failed for '%s', blob stored as fallback",
            name,
        )

    return flow_def_id


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


def read_flow_by_name(
    conn: sqlite3.Connection, name: str, project_root=None
) -> dict | None:
    """Return a single flow definition by name, or None if not found."""
    if project_root is not None:
        row = conn.execute(
            "SELECT * FROM flow_definitions WHERE name=? AND project_root=?",
            (name, project_root),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM flow_definitions WHERE name=? AND project_root IS NULL",
            (name,),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM flow_definitions WHERE name=? ORDER BY project_root IS NULL DESC LIMIT 1",
                (name,),
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
        name = f.stem
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
