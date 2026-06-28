"""Per-artifact AI-summary query helpers (unified-ai-routing, Conv 3).

Split out of comms.py to keep that file under the 400-line SOLID cap (Open/Closed:
new query family → new file, not a longer comms.py). Owns the ``summary_selection``
column added in this conversation plus a thin ``set_artifact_summary`` writer that
reuses the canonical ``update_artifact_summary`` already in comms.py.
"""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock


def set_artifact_summary_selection(
    conn: sqlite3.Connection,
    artifact_id: str,
    selection_json: str,
) -> None:
    """Persist the per-artifact AI target (JSON-encoded AiSelection) for artifact_id.

    selection_json is the raw JSON string the client sends, e.g.
    ``'{"type":"model","id":"phi-4-mini"}'``. Stored verbatim so the renderer's
    AiTargetSelector can round-trip it without re-parsing on the server.
    """
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_artifacts SET summary_selection=? WHERE id=?",
            (selection_json, artifact_id),
        )
        conn.commit()


def set_artifact_summary(
    conn: sqlite3.Connection,
    artifact_id: str,
    summary: str,
    *,
    selection_json: str | None = None,
    token_count: int | None = None,
) -> None:
    """Write a client-computed summary (and, optionally, the target that produced it).

    Reuses the canonical ``update_artifact_summary`` for the summary/token_count write
    so there is one writer for that column, then persists the selection in the same
    call when given. The selection write is skipped when selection_json is None so a
    plain summary post never clobbers a previously-saved target.
    """
    from .comms import update_artifact_summary

    update_artifact_summary(conn, artifact_id, summary, token_count=token_count)
    if selection_json is not None:
        set_artifact_summary_selection(conn, artifact_id, selection_json)


def set_artifact_summary_style(
    conn: sqlite3.Connection,
    artifact_id: str,
    style: str,
) -> None:
    """Persist the per-artifact summary DEPTH style for artifact_id.

    style is one of 'gist' | 'topic-map' | 'detailed' — it selects which
    development/summarize* skill the client composes on the next re-summarize.
    """
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_artifacts SET summary_style=? WHERE id=?",
            (style, artifact_id),
        )
        conn.commit()


def get_artifact_summary_selection(
    conn: sqlite3.Connection,
    artifact_id: str,
) -> str | None:
    """Return the stored summary_selection JSON for artifact_id, or None if unset."""
    row = conn.execute(
        "SELECT summary_selection FROM comms_artifacts WHERE id=?",
        (artifact_id,),
    ).fetchone()
    if row is None:
        return None
    return row["summary_selection"]
