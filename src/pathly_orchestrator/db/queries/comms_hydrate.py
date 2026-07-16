"""Full-fidelity row inserts for board disk-mirror hydration (P2).

``post_message`` only inserts the live-write SUBSET of ``comms_messages`` columns (no
``status``/``read_by``/``acknowledged_by``/``deleted_at``/``superseded_by``/...), so it
cannot round-trip a BOARD.json snapshot row without losing fields. ``insert_message_row``
and ``insert_artifact_row`` take a whole snapshot row dict and insert it AS-IS
(id/ts/status/... all preserved), filtered to the table's real columns and idempotent
via ``INSERT OR IGNORE`` — a colliding id (the row is already in the DB) is a no-op, so
re-hydrating an already-populated board changes nothing. Both are best-effort: never raise.

Split out of ``comms_messages.py`` / ``comms_artifacts.py`` (each already at the
project's 400-line-per-file cap) and re-exported from both for the conventional
per-table import path — same split+re-export pattern as ``catalog_items.py`` /
``catalog_indexers.py`` and ``goals.py`` / ``goals_read.py``.
"""

from __future__ import annotations

import logging
import sqlite3

from ..connection import _get_write_lock

_log = logging.getLogger("pathly.board_mirror")


def _insert_snapshot_row(conn: sqlite3.Connection, table: str, row: dict) -> None:
    """Dynamic ``INSERT OR IGNORE`` of *row* into *table*, filtered to *table*'s real
    columns via ``PRAGMA table_info`` (drops any snapshot-only keys a BOARD.json may
    carry). *table* is always one of the two hardcoded literals below, never external
    input. Best-effort — never raises.
    """
    if not row:
        return
    try:
        cols = {
            c["name"]
            for c in conn.execute(
                f"PRAGMA table_info({table})"
            ).fetchall()  # nosec B608
        }
        keys = [k for k in row.keys() if k in cols]
        if not keys:
            return
        col_list = ", ".join(keys)
        placeholders = ", ".join("?" * len(keys))
        values = [row[k] for k in keys]
        with _get_write_lock(conn):
            conn.execute(
                f"INSERT OR IGNORE INTO {table} ({col_list}) VALUES ({placeholders})",  # nosec B608
                values,
            )
            conn.commit()
    except Exception:
        _log.debug(
            "insert into %s failed for id=%s", table, row.get("id"), exc_info=True
        )


def insert_message_row(conn: sqlite3.Connection, row: dict) -> None:
    """Insert a full ``comms_messages`` snapshot row (hydration). Best-effort — never raises."""
    _insert_snapshot_row(conn, "comms_messages", row)


def insert_artifact_row(conn: sqlite3.Connection, row: dict) -> None:
    """Insert a full ``comms_artifacts`` snapshot row (hydration). Best-effort — never raises."""
    _insert_snapshot_row(conn, "comms_artifacts", row)
