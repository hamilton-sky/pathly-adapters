"""Edit a board message's text — and stamp the row with whoever edited it."""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock
from ..provenance_values import SOURCE_NONE, check_author_source
from ..secret_scan import redact_run_tokens


def update_message_text(
    conn: sqlite3.Connection,
    message_id: str,
    text: str,
    author_role: str | None = None,
    author_run_id: str | None = None,
    author_source: str | None = None,
) -> str:
    """Edit a message's text in place, stamping the row with the editor.

    Returns ``"updated"``, ``"not_found"`` or ``"binding"``. A binding directive
    (``binding = 1``) is superseded, never edited: it answers ``"binding"`` and changes
    nothing. The three author columns are set in the same ``UPDATE`` as the text, as
    ``post_message`` sets them on a new row: the editor's stamp, and ``none`` when
    ``author_source`` is ``None``. A source outside ``AUTHOR_SOURCES`` raises ``ValueError``
    before anything is written. ``text`` is stored with run tokens redacted
    (``db/secret_scan.py``).
    """
    check_author_source(author_source)
    text = redact_run_tokens(conn, text)
    row = conn.execute(
        "SELECT binding FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    if row[0] == 1:
        return "binding"
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
