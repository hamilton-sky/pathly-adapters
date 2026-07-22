"""Query helpers for the fsm_events table."""

from __future__ import annotations

import json
import sqlite3

from ..connection import _get_write_lock


def _norm(project_root: str) -> str:
    """Normalize a project_root to a stable SQLite key.

    Forward-slashes so Windows backslash and HTTP paths hit the same row, AND strip the
    Windows ``\\\\?\\`` extended-length prefix. ``Path.resolve()`` on Windows returns that
    prefix inconsistently — notably for a not-yet-created directory, racing directory
    creation — so without this strip a feature's first event(s) can be written under
    ``//?/C:/...`` while the reader queries ``C:/...`` and silently misses them.
    """
    s = project_root.replace("\\", "/")
    if s.startswith("//?/"):
        s = s[4:]
    return s


def _board_scope_of(event_dict: dict) -> str | None:
    """Extract the run-identity board scope from an event dict (absent → NULL).

    Guarded like the projection's ``category``: an unsubstituted ``<feature>``
    placeholder (a raw/interactive skill that skipped injection) lands as NULL,
    never as a junk identity. The raw value stays in the payload blob regardless.
    """
    v = event_dict.get("board_scope")
    if not isinstance(v, str):
        return None
    v = v.strip()
    if not v or v.startswith("<"):
        return None
    return v


def append_event(
    conn: sqlite3.Connection, project_root: str, feature: str, event_dict: dict
) -> int:
    """Insert *event_dict* into fsm_events. Returns the new seq (lastrowid)."""
    event_type = event_dict.get("type", event_dict.get("event_type", ""))
    ts = event_dict.get("ts", "")
    board_scope = _board_scope_of(event_dict)
    payload = json.dumps(event_dict)
    norm_pr = _norm(project_root)
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO fsm_events (project_root, feature, ts, event_type, payload, board_scope) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (norm_pr, feature, ts, event_type, payload, board_scope),
        )
        conn.commit()
        seq = cur.lastrowid or 0

    # telemetry-reconciliation: project the completion/billing event into
    # agent_invocations so the DB-explorer roll-up + cost chart reflect real cost for
    # EVERY run (not just supervised ones). Outside the write lock, best-effort — a
    # telemetry projection must never break event append.
    if event_type in ("AGENT_DONE", "BILLING_UPDATE") and seq:
        try:
            from .invocation_projection import on_event_appended

            on_event_appended(conn, seq, norm_pr, feature, event_dict)
        except Exception:
            pass
    return seq


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
