"""Query helpers for the runner_state table."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def write_runner_state(
    conn: sqlite3.Connection, project_root: str, feature: str, runner_dict: dict
) -> None:
    """Upsert *runner_dict* into runner_state as JSON."""
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR REPLACE INTO runner_state "
            "(project_root, feature, runner_json, updated_at) "
            "VALUES (?, ?, ?, ?)",
            (
                project_root,
                feature,
                json.dumps(runner_dict),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def read_runner_state(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> dict | None:
    """Return the runner_state row for *project_root*/*feature* as a dict, or None."""
    row = conn.execute(
        "SELECT runner_json FROM runner_state WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["runner_json"])


def mark_stale_runners(conn: sqlite3.Connection) -> int:
    """Set status='error' for all runner_state rows where runner_json contains status='running'.

    Returns the number of rows updated.
    """
    with _get_write_lock(conn):
        rows = conn.execute(
            "SELECT project_root, feature, runner_json FROM runner_state"
        ).fetchall()
        updated = 0
        for row in rows:
            try:
                d = json.loads(row["runner_json"])
            except (json.JSONDecodeError, TypeError):
                continue
            if d.get("status") == "running":
                d["status"] = "error"
                conn.execute(
                    "UPDATE runner_state SET runner_json=? WHERE project_root=? AND feature=?",
                    (json.dumps(d), row["project_root"], row["feature"]),
                )
                updated += 1
        conn.commit()
        return updated
