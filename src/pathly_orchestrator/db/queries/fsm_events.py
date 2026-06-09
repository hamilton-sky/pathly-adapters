"""Query helpers for the fsm_events table."""
from __future__ import annotations

import json
import sqlite3

from ..connection import _get_write_lock


def _norm(project_root: str) -> str:
    """Normalize path separators so Windows backslash and forward-slash paths hit the same row."""
    return project_root.replace("\\", "/")


def append_event(
    conn: sqlite3.Connection, project_root: str, feature: str, event_dict: dict
) -> int:
    """Insert *event_dict* into fsm_events. Returns the new seq (lastrowid)."""
    event_type = event_dict.get("type", event_dict.get("event_type", ""))
    ts = event_dict.get("ts", "")
    payload = json.dumps(event_dict)
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO fsm_events (project_root, feature, ts, event_type, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (_norm(project_root), feature, ts, event_type, payload),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_events(
    conn: sqlite3.Connection, project_root: str, feature: str, since_seq: int = 0
) -> list[dict]:
    """Return all events for *project_root*/*feature* with seq > *since_seq*, ordered by seq."""
    rows = conn.execute(
        "SELECT seq, payload FROM fsm_events "
        "WHERE project_root=? AND feature=? AND seq>? ORDER BY seq ASC",
        (_norm(project_root), feature, since_seq),
    ).fetchall()
    result = []
    for row in rows:
        event = json.loads(row["payload"])
        event["seq"] = row["seq"]
        result.append(event)
    return result


def read_last_agent_done(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> dict | None:
    """Return the payload of the most recent AGENT_DONE event, or None."""
    row = conn.execute(
        "SELECT payload FROM fsm_events "
        "WHERE project_root=? AND feature=? AND event_type='AGENT_DONE' "
        "ORDER BY seq DESC LIMIT 1",
        (_norm(project_root), feature),
    ).fetchone()
    if row is None:
        return None
    return json.loads(row["payload"])
