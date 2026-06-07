"""Query helpers for the fsm_state table."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def write_state(
    conn: sqlite3.Connection, project_root: str, feature: str, state_dict: dict
) -> None:
    """Upsert *state_dict* into fsm_state as JSON."""
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR REPLACE INTO fsm_state (project_root, feature, state_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                project_root,
                feature,
                json.dumps(state_dict),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def read_state(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> dict | None:
    """Return the fsm_state row for *project_root*/*feature* as a dict, or None."""
    row = conn.execute(
        "SELECT state_json FROM fsm_state WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["state_json"])
