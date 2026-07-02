"""Artifact metadata CRUD — comms_artifacts and comms_artifact_sections tables."""

from __future__ import annotations

import sqlite3
import uuid
from typing import Any

from ..connection import _get_write_lock
from .comms_messages import _now, post_message


def attach_artifact_to_message(
    conn: sqlite3.Connection,
    message_id: str,
    artifact_path: str | None = None,
    artifact_type: str | None = None,
    artifact_url: str | None = None,
) -> str:
    """Set artifact_* fields on an existing message. Returns 'ok' | 'not_found'."""
    row = conn.execute(
        "SELECT board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages "
            "SET artifact_path=?, artifact_type=?, artifact_url=? WHERE id=?",
            (artifact_path, artifact_type, artifact_url, message_id),
        )
        conn.commit()
    return "ok"


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


def list_artifacts_for_message(conn: sqlite3.Connection, message_id: str) -> list[dict]:
    """Return every artifact linked to a message, newest first."""
    rows = conn.execute(
        "SELECT * FROM comms_artifacts WHERE message_id=? ORDER BY created_at DESC",
        (message_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def reindex_artifact_sections(
    conn: sqlite3.Connection,
    artifact_id: str,
    sections: list[dict],
    mtime: float,
    content_hash: str,
    structure_key: str,
) -> None:
    """Replace all section rows for artifact_id and stamp staleness fingerprints."""
    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM comms_artifact_sections WHERE artifact_id=?", (artifact_id,)
        )
        for sec in sections:
            conn.execute(
                "INSERT INTO comms_artifact_sections "
                "(id, artifact_id, anchor, heading, line_start, line_end, ordinal) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    sec["id"],
                    artifact_id,
                    sec["anchor"],
                    sec.get("heading"),
                    sec["line_start"],
                    sec["line_end"],
                    sec.get("ordinal", 0),
                ),
            )
        conn.execute(
            "UPDATE comms_artifacts SET indexed_mtime=?, indexed_hash=?, indexed_structure_key=? "
            "WHERE id=?",
            (mtime, content_hash, structure_key, artifact_id),
        )
        conn.commit()


def update_artifact_indexed_mtime(
    conn: sqlite3.Connection,
    artifact_id: str,
    mtime: float,
) -> None:
    """Update only indexed_mtime for artifact_id (mtime moved, content unchanged)."""
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_artifacts SET indexed_mtime=? WHERE id=?",
            (mtime, artifact_id),
        )
        conn.commit()


def get_artifact_sections(conn: sqlite3.Connection, artifact_id: str) -> list[dict]:
    """Return all section rows for artifact_id, ordered by ordinal."""
    rows = conn.execute(
        "SELECT * FROM comms_artifact_sections WHERE artifact_id=? ORDER BY ordinal ASC",
        (artifact_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_section(conn: sqlite3.Connection, artifact_id: str, anchor: str) -> dict | None:
    """Return the section row for (artifact_id, anchor), or None if absent."""
    row = conn.execute(
        "SELECT * FROM comms_artifact_sections WHERE artifact_id=? AND anchor=?",
        (artifact_id, anchor),
    ).fetchone()
    return dict(row) if row is not None else None


def find_or_create_artifact_by_path(
    conn: sqlite3.Connection, scope: str, path: str
) -> dict | None:
    """Resolve a comms_artifacts row by (scope, path), creating a sentinel for legacy plans."""
    import os

    row = conn.execute(
        "SELECT a.* FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE m.scope=? AND a.path=? "
        "ORDER BY a.created_at DESC LIMIT 1",
        (scope, path),
    ).fetchone()
    if row is not None:
        return dict(row)

    if not os.path.exists(path):
        return None

    normalized_path = path.replace("\\", "/")
    # Sentinel rows are created only for artifacts under a known pathly/ subtree.
    # The storage-restructure moved feature homes to pathly/features/ (project scope
    # to pathly/project/), so those must be recognized alongside the legacy plans/goals
    # dirs — otherwise context_refs pointing at pathly/features/<f>/*.md 404 on hydrate.
    _allowed_roots = (
        "/pathly/features/",
        "/pathly/plans/",
        "/pathly/goals/",
        "/pathly/project/",
    )
    if not any(seg in normalized_path for seg in _allowed_roots):
        return None

    sentinel_artifact_id = str(uuid.uuid4())
    sentinel_msg_id = str(uuid.uuid4())
    title = path.replace("\\", "/").rsplit("/", 1)[-1]
    now = _now()
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_messages "
            "(id, board, scope, from_agent, to_agent, type, text, ts) "
            "VALUES (?, 'feature', ?, 'system', '*', 'artifact', ?, ?)",
            (sentinel_msg_id, scope, f"[legacy artifact] {title}", now),
        )
        conn.execute(
            "INSERT INTO comms_artifacts "
            "(id, message_id, path, type, title, created_at, created_by, version) "
            "VALUES (?, ?, ?, 'md', ?, ?, 'system', 1)",
            (sentinel_artifact_id, sentinel_msg_id, path, title, now),
        )
        conn.commit()

    return {
        "id": sentinel_artifact_id,
        "message_id": sentinel_msg_id,
        "path": path,
        "type": "md",
        "title": title,
        "summary": None,
        "indexed_mtime": None,
        "indexed_hash": None,
        "indexed_structure_key": None,
    }


def ensure_attached(
    conn: sqlite3.Connection,
    scope: str,
    artifact_path: str,
    *,
    board: str = "feature",
    goal_id: str | None = None,
    role: str | None = None,
    title: str | None = None,
    summary: str | None = None,
    type: str = "md",
    broadcast_fn=None,
) -> dict:
    """Idempotently ensure an artifact at (scope, artifact_path) is on the board.

    Idempotent on (scope, artifact_path): a second call returns the SAME artifact id
    and creates no duplicate row/message. If broadcast_fn is provided, emits an
    'artifact_attached' event (injected callback — SSE concerns stay out of db layer).
    Returns the artifact row dict.
    """
    existing = conn.execute(
        "SELECT a.* FROM comms_artifacts a "
        "JOIN comms_messages m ON m.id = a.message_id "
        "WHERE m.scope=? AND a.path=? "
        "ORDER BY a.created_at DESC LIMIT 1",
        (scope, artifact_path),
    ).fetchone()
    if existing is not None:
        return dict(existing)

    fname = artifact_path.replace("\\", "/").rsplit("/", 1)[-1]
    msg_id = post_message(
        conn,
        board=board,
        scope=scope,
        from_agent=(role or "system"),
        type="artifact",
        text=(summary or f"Artifact: {title or fname}"),
        artifact_path=artifact_path,
        artifact_type=type,
        goal_id=goal_id,
    )
    artifact_id = insert_artifact(
        conn,
        message_id=msg_id,
        path=artifact_path,
        type=type,
        title=(title or fname),
        summary=summary,
        created_by=(role or "system"),
    )
    if broadcast_fn is not None:
        try:
            broadcast_fn({"type": "artifact_attached", "scope": scope,
                          "path": artifact_path, "artifact_id": artifact_id,
                          "goal_id": goal_id})
        except Exception:
            pass
    row = conn.execute("SELECT * FROM comms_artifacts WHERE id=?", (artifact_id,)).fetchone()
    return dict(row) if row is not None else {"id": artifact_id, "path": artifact_path}


def list_artifacts_catalog(
    conn: sqlite3.Connection,
    scope: str,
    exposed_boards: list[str],
    *,
    goal_id: str | None = None,
    order: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[dict]:
    """Board Catalog query: deterministic listing of artifacts for a scope."""
    if not exposed_boards:
        return []
    board_ph = ",".join("?" * len(exposed_boards))
    params: list[Any] = list(exposed_boards) + [scope]
    goal_clause = ""
    if goal_id is not None:
        goal_clause = " AND m.goal_id=?"
        params.append(goal_id)
    order_clause = "ORDER BY a.type, a.path"
    if order == "recency":
        order_clause = "ORDER BY a.created_at DESC"
    limit_clause = ""
    if limit is not None:
        limit_clause = " LIMIT ?"
        params.append(limit)
        if offset is not None:
            limit_clause += " OFFSET ?"
            params.append(offset)
    sql = (
        f"SELECT a.path, a.type, a.title, a.summary "  # nosec B608
        f"FROM comms_artifacts a "
        f"JOIN comms_messages m ON m.id = a.message_id "
        f"WHERE m.board IN ({board_ph}) AND m.scope=? AND m.deleted_at IS NULL"
        f"{goal_clause} {order_clause}{limit_clause}"
    )
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def update_artifact_summary(
    conn: sqlite3.Connection,
    artifact_id: str,
    summary: str,
    token_count: int | None = None,
) -> None:
    """Overwrite comms_artifacts.summary (and optionally token_count) for artifact_id."""
    with _get_write_lock(conn):
        if token_count is not None:
            conn.execute(
                "UPDATE comms_artifacts SET summary=?, token_count=? WHERE id=?",
                (summary, token_count, artifact_id),
            )
        else:
            conn.execute(
                "UPDATE comms_artifacts SET summary=? WHERE id=?",
                (summary, artifact_id),
            )
        conn.commit()
