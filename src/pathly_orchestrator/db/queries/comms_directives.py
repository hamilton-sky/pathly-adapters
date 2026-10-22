"""Binding decisions (standing orders) — the rows a prompt carries whatever their status."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .comms_messages import post_message


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


def post_directive(
    conn: sqlite3.Connection, scope: str, to_agent: str, text: str, **author: Any
) -> str:
    """Post a binding directive on the project board of *scope* and return its id.

    The one writer that sets ``binding = 1``: a ``decision`` from ``chief`` to *to_agent*
    (``*`` or a role), written by ``post_message`` with ``binding=1`` in its one INSERT. There
    is no second statement that could fail and leave an ordinary pending decision (which every
    role's prompt carries as a normal decision) behind, to be copied by a retry. *author* is
    the ``author_*`` stamp of the caller (``runner.provenance.stamp``). *scope* is the project root
    as ``fsm_compose.resolve_board_scope("project", root, "")`` gives it, which is the scope a
    prompt reads the standing orders of the project from. The caller checks the fields.
    """
    return post_message(
        conn,
        board="project",
        scope=scope,
        from_agent="chief",
        to_agent=to_agent,
        type="decision",
        text=text,
        binding=1,
        **author,
    )
