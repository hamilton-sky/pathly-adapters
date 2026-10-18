"""Chief sessions, the human messages typed into them, and the citations of those messages."""

from __future__ import annotations

import sqlite3
import time

from ..connection import _get_write_lock
from .run_tokens import revoke_run_tokens

STALE_REASON = "server restart"


def _one(cur: sqlite3.Cursor) -> dict | None:
    row = cur.fetchone()
    if row is None:
        return None
    keys = [d[0] for d in cur.description]
    return dict(zip(keys, tuple(row)))


def create_session(
    conn: sqlite3.Connection,
    *,
    run_id: str,
    project_root: str,
    preset: str | None,
    tier: str,
    engine: str,
    tab_id: str | None,
    cli_session_id: str | None,
    hook_secret_hash: str | None,
    settings_dir: str | None,
) -> None:
    """Register an open chief session; ``cli_session_id`` is None for an engine without one."""
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO chief_sessions (run_id, project_root, preset, tier, engine, tab_id,"
            " cli_session_id, hook_secret_hash, settings_dir, opened_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                project_root,
                preset,
                tier,
                engine,
                tab_id,
                cli_session_id,
                hook_secret_hash,
                settings_dir,
                time.time(),
            ),
        )
        conn.commit()


def get_session(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """The session row of ``run_id``, open or closed, or None."""
    return _one(
        conn.execute("SELECT * FROM chief_sessions WHERE run_id = ?", (run_id,))
    )


def open_session_for_project(
    conn: sqlite3.Connection, project_root: str
) -> dict | None:
    """The session of ``project_root`` that is not closed yet, or None."""
    return _one(
        conn.execute(
            "SELECT * FROM chief_sessions WHERE project_root = ? AND closed_at IS NULL"
            " ORDER BY opened_at DESC LIMIT 1",
            (project_root,),
        )
    )


def close_session(conn: sqlite3.Connection, run_id: str, reason: str) -> bool:
    """Close an open session once and revoke the run's tokens.

    Returns False, writing nothing, when the session is unknown or was already closed. The
    tokens are revoked before the session is marked closed, so a failure in between leaves an
    open session with a dead token (``close_stale_sessions`` closes it at the next start),
    never a closed session with a live token.
    """
    with _get_write_lock(conn):
        still_open = conn.execute(
            "SELECT 1 FROM chief_sessions WHERE run_id = ? AND closed_at IS NULL",
            (run_id,),
        ).fetchone()
        if still_open is None:
            return False
        revoke_run_tokens(conn, run_id)
        conn.execute(
            "UPDATE chief_sessions SET closed_at = ?, close_reason = ?"
            " WHERE run_id = ? AND closed_at IS NULL",
            (time.time(), reason, run_id),
        )
        conn.commit()
        return True


def close_stale_sessions(conn: sqlite3.Connection) -> list[str]:
    """Close every open session (its tab died with the server); returns their run ids."""
    with _get_write_lock(conn):
        open_ids = [
            row[0]
            for row in conn.execute(
                "SELECT run_id FROM chief_sessions WHERE closed_at IS NULL"
            ).fetchall()
        ]
        return [rid for rid in open_ids if close_session(conn, rid, STALE_REASON)]


def add_human_message(
    conn: sqlite3.Connection,
    run_id: str,
    project_root: str | None,
    text: str,
    *,
    relayed: bool = False,
) -> dict:
    """Store a prompt typed into the session; returns ``{id, kind, ts}``.

    The first message of a session is its ``style_prompt`` whatever ``relayed`` says; every
    later one is ``human``, or ``relayed`` when it came from another session.
    """
    with _get_write_lock(conn):
        seen = conn.execute(
            "SELECT 1 FROM chief_human_messages WHERE run_id = ? LIMIT 1", (run_id,)
        ).fetchone()
        if seen is None:
            kind = "style_prompt"
        else:
            kind = "relayed" if relayed else "human"
        ts = time.time()
        cur = conn.execute(
            "INSERT INTO chief_human_messages (run_id, project_root, kind, text, ts)"
            " VALUES (?, ?, ?, ?, ?)",
            (run_id, project_root, kind, text, ts),
        )
        conn.commit()
        return {"id": cur.lastrowid, "kind": kind, "ts": ts}


def get_human_message(conn: sqlite3.Connection, message_id: int) -> dict | None:
    """The stored message ``message_id``, or None."""
    return _one(
        conn.execute("SELECT * FROM chief_human_messages WHERE id = ?", (message_id,))
    )


def record_citation(
    conn: sqlite3.Connection,
    run_id: str,
    message_id: int,
    route: str,
    target: str | None,
) -> bool:
    """Record that ``message_id`` was cited; False, nothing written, when it already was."""
    try:
        with _get_write_lock(conn):
            conn.execute(
                "INSERT INTO chief_citations (run_id, message_id, route, target, ts)"
                " VALUES (?, ?, ?, ?, ?)",
                (run_id, message_id, route, target, time.time()),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return False
    return True
