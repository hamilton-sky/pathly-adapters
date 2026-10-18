"""Edit a board message's text — and stamp the row with whoever edited it."""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock
from ..provenance_values import AUTHOR_SOURCES, SOURCE_NONE


def update_message_text(
    conn: sqlite3.Connection,
    message_id: str,
    text: str,
    author_role: str | None = None,
    author_run_id: str | None = None,
    author_source: str | None = None,
) -> str:
    """Edit a message's text in place, stamping the row with the editor.

    Returns ``"updated"`` or ``"not_found"``. The three author columns are set in the same
    ``UPDATE`` as the text, as ``post_message`` sets them on a new row: the editor's stamp,
    and ``none`` when ``author_source`` is ``None``. A source outside ``AUTHOR_SOURCES``
    raises ``ValueError`` before anything is written.
    """
    if author_source is not None and author_source not in AUTHOR_SOURCES:
        raise ValueError(
            f"unknown author_source {author_source!r}; expected one of {sorted(AUTHOR_SOURCES)}"
        )
    row = conn.execute(
        "SELECT id FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET text=?, author_role=?, author_run_id=?, "
            "author_source=? WHERE id=?",
            (
                text,
                author_role,
                author_run_id,
                author_source or SOURCE_NONE,
                message_id,
            ),
        )
        conn.commit()
    return "updated"
