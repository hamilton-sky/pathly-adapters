"""Binding decisions (standing orders) — the rows a prompt carries whatever their status."""

from __future__ import annotations

import json
import sqlite3


def get_binding_decisions(
    conn: sqlite3.Connection,
    boards: list[str],
    scopes: list[str],
    role: str,
) -> list[dict]:
    """Return the binding decisions for *role* on the given boards/scopes, oldest first.

    ``binding = 1`` decisions of any ``status`` (an acknowledgement does not retire one),
    not deleted and not superseded, addressed to *role* or to ``*``. An empty *role* takes
    only the ``*`` ones, so a prompt composed without a role never gets another role's order.

    The board and scope lists go in as one JSON string each and ``json_each`` unpacks them,
    so the statement is one static literal whatever the lists hold. ``json_each`` is built
    into SQLite since 3.38.0.
    """
    if not boards or not scopes:
        return []
    rows = conn.execute(
        "SELECT * FROM comms_messages "
        "WHERE board IN (SELECT value FROM json_each(?)) "
        "AND scope IN (SELECT value FROM json_each(?)) "
        "AND type='decision' AND binding=1 AND deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by = '') "
        "AND to_agent IN ('*', ?) "
        "ORDER BY ts ASC",
        (json.dumps(list(boards)), json.dumps(list(scopes)), role or "*"),
    ).fetchall()
    return [dict(r) for r in rows]
