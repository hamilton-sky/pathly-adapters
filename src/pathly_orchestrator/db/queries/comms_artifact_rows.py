"""The comms_artifacts board-row insert (moved out of comms_artifacts.py, at its 400-line cap).

Re-exported from ``comms_artifacts`` and ``comms``, so ``from ...comms_artifacts import
insert_artifact`` keeps working. ``title`` and ``summary`` are stored with run tokens
redacted (``db/secret_scan.py``).
"""

from __future__ import annotations

import sqlite3
import uuid

from ..connection import _get_write_lock
from ..secret_scan import redact_run_tokens
from .comms_messages import _now


def insert_artifact(
    conn: sqlite3.Connection,
    message_id: str,
    path: str,
    type: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    token_count: int | None = None,
    created_by: str | None = None,
) -> str:
    """Insert a comms_artifacts row. Idempotent per (message_id, path). Returns the row id."""
    existing = conn.execute(
        "SELECT id FROM comms_artifacts WHERE message_id=? AND path=?",
        (message_id, path),
    ).fetchone()
    if existing is not None:
        return existing["id"]
    artifact_id = str(uuid.uuid4())
    if title is None and path:
        title = path.replace("\\", "/").rsplit("/", 1)[-1]
    title = redact_run_tokens(conn, title)
    summary = redact_run_tokens(conn, summary)
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_artifacts "
            "(id, message_id, path, type, title, summary, token_count, created_at, created_by, version) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)",
            (
                artifact_id,
                message_id,
                path,
                type,
                title,
                summary,
                token_count,
                _now(),
                created_by,
            ),
        )
        conn.commit()
    return artifact_id
