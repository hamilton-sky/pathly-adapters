"""run_log store: per-spawn prompt / board-context / stdin / stdout (unified-control-plane P0)."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock
from ..secret_scan import redact_run_tokens


def write_run_log_spawn(
    conn: sqlite3.Connection,
    run_id: str,
    stage: str | None,
    prompt_sent: str | None,
    board_context_injected: str | None = None,
    stdin: str | None = None,
) -> None:
    """INSERT the spawn-time half (prompt + board context + stdin). Best-effort caller.

    Each text is stored with run tokens redacted (``db/secret_scan.py``).
    """
    prompt_sent = redact_run_tokens(conn, prompt_sent)
    board_context_injected = redact_run_tokens(conn, board_context_injected)
    stdin = redact_run_tokens(conn, stdin)
    ts = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO run_log (run_id, stage, prompt_sent, board_context_injected, stdin, stdout, ts) "
            "VALUES (?, ?, ?, ?, ?, NULL, ?)",
            (run_id, stage, prompt_sent, board_context_injected, stdin, ts),
        )
        conn.commit()


def update_run_log_stdout(
    conn: sqlite3.Connection, run_id: str, stdout: str | None
) -> None:
    """Fill the result-time half (stdout) for the newest row of run_id. No-op if no spawn row.

    ``stdout`` is stored with run tokens redacted (``db/secret_scan.py``).
    """
    stdout = redact_run_tokens(conn, stdout)
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE run_log SET stdout=? WHERE id=("
            "  SELECT id FROM run_log WHERE run_id=? ORDER BY id DESC LIMIT 1)",
            (stdout, run_id),
        )
        conn.commit()


def get_run_log(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """All run_log rows for run_id (positional-safe via dict(row))."""
    rows = conn.execute(
        "SELECT * FROM run_log WHERE run_id=? ORDER BY id ASC", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]
