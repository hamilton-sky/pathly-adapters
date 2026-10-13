"""Mint, resolve and revoke per-run tokens (the server-issued identity of one spawn).

Only sha256(token) is stored; the raw token exists in the caller's hands alone.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time

from ..connection import _get_write_lock


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def mint_run_token(
    conn: sqlite3.Connection,
    run_id: str,
    role: str | None,
    feature: str | None,
    project_root: str | None,
    board: str | None,
    scope: str | None,
) -> str:
    """Issue a token for ``run_id``; returns the raw token (stored hashed)."""
    token = secrets.token_urlsafe(32)
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO run_tokens "
            "(token_hash, run_id, role, feature, project_root, board, scope, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                _hash(token),
                run_id,
                role,
                feature,
                project_root,
                board,
                scope,
                time.time(),
            ),
        )
        conn.commit()
    return token


def resolve_run_token(conn: sqlite3.Connection, token: str | None) -> dict | None:
    """The identity row for a live token, or None (unknown, revoked, empty or missing)."""
    if not token:
        return None
    row = conn.execute(
        "SELECT * FROM run_tokens WHERE token_hash = ? AND revoked_at IS NULL",
        (_hash(token),),
    ).fetchone()
    if row is None:
        return None
    keys = [d[0] for d in conn.execute("SELECT * FROM run_tokens LIMIT 0").description]
    return dict(zip(keys, tuple(row)))


def revoke_run_tokens(conn: sqlite3.Connection, run_id: str) -> int:
    """Revoke every live token of ``run_id``; returns how many were revoked."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE run_tokens SET revoked_at = ? WHERE run_id = ? AND revoked_at IS NULL",
            (time.time(), run_id),
        )
        conn.commit()
        return cur.rowcount
