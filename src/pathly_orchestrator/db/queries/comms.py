"""Query helpers for the comms_messages and comms_embeddings tables."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from .. import connection as _connection_module
from ..connection import _get_write_lock, _VEC_AVAILABLE


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def post_message(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    from_agent: str,
    to_agent: str = "*",
    type: str = "nudge",
    text: str = "",
    options: list | None = None,
    reply_to: str | None = None,
    stage: str | None = None,
    conv: int | None = None,
    depends_on: list[str] | None = None,
    artifact_path: str | None = None,
    artifact_type: str | None = None,
    goal_id: str | None = None,
    executor: str | None = None,
) -> str:
    """Insert a new message into comms_messages. Returns the new message_id.

    goal_id ties a task to its goal message; executor ('single'|'loop'|'team')
    is set on the goal message only. Both default to None so existing callers
    keep their behavior (the columns are harmlessly NULL).
    """
    message_id = str(uuid.uuid4())
    # A task enters the DAG frontier as 'pending' so get_ready_tasks() (which
    # filters task_status='pending') can pick it up. Non-task messages leave it NULL.
    task_status = "pending" if type == "task" else None
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_messages "
            "(id, board, scope, from_agent, to_agent, type, text, options, reply_to, stage, conv, ts, depends_on, task_status, artifact_path, artifact_type, goal_id, executor) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                message_id,
                board,
                scope,
                from_agent,
                to_agent,
                type,
                text,
                json.dumps(options) if options is not None else None,
                reply_to,
                stage,
                conv,
                _now(),
                json.dumps(depends_on) if depends_on is not None else None,
                task_status,
                artifact_path,
                artifact_type,
                goal_id,
                executor,
            ),
        )
        conn.commit()
    return message_id


def get_messages(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return messages for the given board/scope, newest first."""
    sql = "SELECT * FROM comms_messages WHERE board=? AND scope=? AND deleted_at IS NULL"
    params: list[Any] = [board, scope]
    if type is not None:
        sql += " AND type=?"
        params.append(type)
    if status is not None:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def search_by_embedding(
    conn: sqlite3.Connection,
    embedding: list[float],
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """Return up to k messages ordered by semantic similarity (or recency when vec unavailable)."""
    if not boards or not scopes:
        return []
    if _VEC_AVAILABLE:
        board_ph = ",".join("?" * len(boards))
        scope_ph = ",".join("?" * len(scopes))
        import struct
        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
        sql = (
            "SELECT m.* FROM comms_messages m "
            "JOIN comms_embeddings e ON e.message_id = m.id "
            f"WHERE m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
            "AND m.deleted_at IS NULL "
            "ORDER BY vec_distance_cosine(e.embedding, ?) ASC "
            "LIMIT ?"
        )
        params: list[Any] = list(boards) + list(scopes) + [embedding_bytes, k]
        rows = conn.execute(sql, params).fetchall()
    else:
        board_ph = ",".join("?" * len(boards))
        scope_ph = ",".join("?" * len(scopes))
        sql = (
            "SELECT * FROM comms_messages "
            f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
            "AND deleted_at IS NULL "
            "ORDER BY ts DESC LIMIT ?"
        )
        params = list(boards) + list(scopes) + [k]
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


_RRF_K = 60


def search_by_keyword(
    conn: sqlite3.Connection,
    query_text: str,
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """BM25 full-text search via FTS5. Returns [] when FTS unavailable or inputs empty."""
    if not _connection_module._FTS_AVAILABLE or not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT m.* FROM comms_messages m "
        "JOIN comms_fts ON comms_fts.rowid = m.rowid "
        f"WHERE comms_fts MATCH ? AND m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
        "AND m.deleted_at IS NULL "
        "ORDER BY rank LIMIT ?"
    )
    try:
        rows = conn.execute(sql, [query_text] + list(boards) + list(scopes) + [k]).fetchall()
    except sqlite3.OperationalError:
        return []
    return [dict(r) for r in rows]


def search_by_hybrid(
    conn: sqlite3.Connection,
    query_text: str,
    query_embedding: list[float] | None,
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """BM25 + cosine merged via Reciprocal Rank Fusion. Falls back gracefully.

    When query_embedding is None, falls back to keyword-only (then recency if
    FTS also unavailable). When query_text is empty, falls back to semantic-only.
    """
    bm25_rows = search_by_keyword(conn, query_text, boards, scopes, k * 2) if query_text else []
    sem_rows = (
        search_by_embedding(conn, query_embedding, boards, scopes, k * 2)
        if query_embedding is not None
        else []
    )

    if not bm25_rows and not sem_rows:
        return []

    scores: dict[str, dict] = {}
    for rank, row in enumerate(bm25_rows):
        mid = row["id"]
        scores.setdefault(mid, {"row": row, "bm25": 9999, "sem": 9999})
        scores[mid]["bm25"] = rank
    for rank, row in enumerate(sem_rows):
        mid = row["id"]
        scores.setdefault(mid, {"row": row, "bm25": 9999, "sem": 9999})
        scores[mid]["sem"] = rank

    ranked = sorted(
        scores.values(),
        key=lambda x: 1.0 / (_RRF_K + x["bm25"]) + 1.0 / (_RRF_K + x["sem"]),
        reverse=True,
    )
    return [r["row"] for r in ranked[:k]]


def get_pending_decisions(
    conn: sqlite3.Connection,
    boards: list[str],
    scopes: list[str],
) -> list[dict]:
    """Return all unacknowledged decision messages across the given boards/scopes."""
    if not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT * FROM comms_messages "
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        "AND type='decision' AND status='pending' AND deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by = '') "
        "ORDER BY ts ASC"
    )
    rows = conn.execute(sql, list(boards) + list(scopes)).fetchall()
    return [dict(r) for r in rows]


def supersede_message(conn: sqlite3.Connection, old_id: str, new_id: str) -> str:
    """Mark old_id as superseded by new_id. Returns 'ok'|'not_found'|'already_superseded'."""
    row = conn.execute(
        "SELECT superseded_by FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (old_id,)
    ).fetchone()
    if row is None:
        return "not_found"
    if row["superseded_by"]:
        return "already_superseded"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET superseded_by=? WHERE id=?",
            (new_id, old_id)
        )
        conn.commit()
    return "ok"


def get_active_escalations(
    conn: sqlite3.Connection,
    boards: list[str],
    scopes: list[str],
) -> list[dict]:
    """Return all unresolved escalation messages for the given boards/scopes."""
    if not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT * FROM comms_messages "
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        "AND type='escalation' AND status='pending' AND deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by = '') "
        "ORDER BY ts ASC"
    )
    return [dict(r) for r in conn.execute(sql, list(boards) + list(scopes)).fetchall()]


def attach_artifact_to_message(
    conn: sqlite3.Connection,
    message_id: str,
    artifact_path: str | None = None,
    artifact_type: str | None = None,
    artifact_url: str | None = None,
) -> str:
    """Set artifact_* fields on an existing message.

    Returns 'ok' | 'not_found'. Mirrors supersede_message()'s status-string
    contract so the route can map to 404 cleanly.
    Reuses the already-present artifact_path / artifact_type / artifact_url
    columns (migrations.py:237-239); never creates a new row.
    """
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
    """Insert a comms_artifacts row for an artifact message. Returns the row id.

    Idempotent per (message_id, path): if a row already exists for this message
    and path, returns its id without inserting, so re-posts and back-fills never
    duplicate. ``version`` defaults to 1 and ``last_edit_*`` / ``supersedes``
    stay NULL — the hooks that populate them (editor-save, versioning) are a
    deferred follow-up.
    """
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
            (artifact_id, message_id, path, type, title, summary, token_count, _now(), created_by),
        )
        conn.commit()
    return artifact_id


def list_artifacts_for_message(conn: sqlite3.Connection, message_id: str) -> list[dict]:
    """Return every artifact linked to a message, newest first (many-per-task)."""
    rows = conn.execute(
        "SELECT * FROM comms_artifacts WHERE message_id=? ORDER BY created_at DESC",
        (message_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def acknowledge_message(
    conn: sqlite3.Connection,
    message_id: str,
    agent: str,
) -> None:
    """Add *agent* to acknowledged_by for the given message and mark status=active."""
    row = conn.execute(
        "SELECT acknowledged_by FROM comms_messages WHERE id=?", (message_id,)
    ).fetchone()
    if row is None:
        return
    acknowledged: list = json.loads(row["acknowledged_by"] or "[]")
    if agent not in acknowledged:
        acknowledged.append(agent)
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET acknowledged_by=?, status='active' WHERE id=?",
            (json.dumps(acknowledged), message_id),
        )
        conn.commit()


def answer_question(
    conn: sqlite3.Connection,
    question_id: str,
    answer_text: str,
    option_id: str | None = None,
) -> str:
    """Post an answer message replying to *question_id*. Returns the new message_id."""
    row = conn.execute(
        "SELECT board, scope FROM comms_messages WHERE id=?", (question_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"No message found with id={question_id!r}")
    answer_id = post_message(
        conn,
        board=row["board"],
        scope=row["scope"],
        from_agent="human",
        to_agent="*",
        type="answer",
        text=answer_text,
        reply_to=question_id,
    )
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET status='resolved' WHERE id=?",
            (question_id,),
        )
        conn.commit()
    return answer_id


def store_embedding(
    conn: sqlite3.Connection,
    message_id: str,
    embedding: list[float],
    chunk_index: int = 0,
    chunk_text: str = "",
) -> None:
    """Insert or replace an embedding row in comms_embeddings. No-op if vec unavailable."""
    if not _VEC_AVAILABLE:
        return
    import struct
    embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
    with _get_write_lock(conn):
        conn.execute(
            "INSERT OR REPLACE INTO comms_embeddings (message_id, embedding, chunk_index, chunk_text) "
            "VALUES (?, ?, ?, ?)",
            (message_id, embedding_bytes, chunk_index, chunk_text),
        )
        conn.commit()


def get_trash(
    conn: sqlite3.Connection,
    scope: str,
) -> list[dict]:
    """Return all soft-deleted messages for *scope*."""
    rows = conn.execute(
        "SELECT * FROM comms_messages WHERE scope=? AND deleted_at IS NOT NULL ORDER BY deleted_at DESC",
        (scope,),
    ).fetchall()
    return [dict(r) for r in rows]


def restore_messages(
    conn: sqlite3.Connection,
    message_ids: list[str],
) -> None:
    """Clear deleted_at and restore status to pending for the given message IDs."""
    if not message_ids:
        return
    ph = ",".join("?" * len(message_ids))
    with _get_write_lock(conn):
        conn.execute(
            f"UPDATE comms_messages SET deleted_at=NULL, status='pending' WHERE id IN ({ph})",
            message_ids,
        )
        conn.commit()


def purge_expired_trash(
    conn: sqlite3.Connection,
    days: int = 30,
) -> int:
    """Hard-delete messages trashed more than *days* ago. Returns the count removed."""
    cutoff = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        cur = conn.execute(
            "DELETE FROM comms_messages "
            "WHERE deleted_at IS NOT NULL "
            "AND datetime(deleted_at) <= datetime(?, ?)",
            (cutoff, f"-{days} days"),
        )
        conn.commit()
        return cur.rowcount


def get_ready_tasks(
    conn: sqlite3.Connection,
    boards: list[str],
    scopes: list[str],
    goal_id: str | None = None,
) -> list[dict]:
    """Return task messages where every depends_on ID has task_status='done'.
    A task with depends_on=NULL or depends_on='[]' is always ready if pending.

    When goal_id is given, the frontier is scoped to that goal's tasks only — the
    Phase-1 dispatcher uses this so one goal's loop drains only its own DAG (a
    scope may hold several goals). None-default keeps the board+scope behavior."""
    if not boards or not scopes:
        return []
    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    goal_clause = " AND goal_id=?" if goal_id is not None else ""
    goal_param = [goal_id] if goal_id is not None else []
    pending_sql = (
        "SELECT * FROM comms_messages "
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        f"AND type='task' AND task_status='pending' AND deleted_at IS NULL{goal_clause}"
    )
    pending_rows = conn.execute(
        pending_sql, list(boards) + list(scopes) + goal_param
    ).fetchall()

    done_sql = (
        "SELECT id FROM comms_messages "
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        f"AND type='task' AND task_status='done' AND deleted_at IS NULL{goal_clause}"
    )
    done_ids = {
        r["id"]
        for r in conn.execute(done_sql, list(boards) + list(scopes) + goal_param).fetchall()
    }

    ready = []
    for row in pending_rows:
        deps = json.loads(row["depends_on"] or "[]")
        if all(dep in done_ids for dep in deps):
            ready.append(dict(row))
    return ready


def complete_task(
    conn: sqlite3.Connection,
    message_id: str,
) -> list[str]:
    """Set task_status='done' on message_id. Returns list of message IDs that
    became newly ready (all their deps now done). Idempotent: completing an
    already-done task returns [] with no DB write."""
    row = conn.execute(
        "SELECT board, scope, task_status FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return []
    if row["task_status"] == "done":
        return []

    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET task_status='done' WHERE id=?",
            (message_id,),
        )
        conn.commit()

    board = row["board"]
    scope = row["scope"]

    done_ids = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM comms_messages "
            "WHERE board=? AND scope=? AND type='task' AND task_status='done' AND deleted_at IS NULL",
            (board, scope),
        ).fetchall()
    }

    candidate_rows = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND task_status='pending' AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()

    newly_ready = []
    for candidate in candidate_rows:
        deps = json.loads(candidate["depends_on"] or "[]")
        if deps and message_id in deps and all(dep in done_ids for dep in deps):
            newly_ready.append(candidate["id"])
    return newly_ready


def claim_task(conn: sqlite3.Connection, message_id: str, run_id: str) -> bool:
    """Atomically transition pending → in_progress.

    Returns True if this caller won the claim, False if the task was already
    claimed, done, or failed. The WHERE clause is the compare-and-set: only one
    concurrent caller can flip a pending row.
    """
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE comms_messages "
            "SET task_status='in_progress', claimed_at=?, claimed_by=?, "
            "    attempts=COALESCE(attempts, 0)+1 "
            "WHERE id=? AND task_status='pending' AND deleted_at IS NULL",
            (now, run_id, message_id),
        )
        conn.commit()
    return cur.rowcount == 1


def fail_task(conn: sqlite3.Connection, message_id: str, reason: str = "") -> list[str]:
    """Mark a task failed and BFS-cascade transitive dependents to 'blocked'.

    Returns the list of blocked dependent IDs. Idempotent: a task already
    'failed' returns [] with no DB write.
    """
    row = conn.execute(
        "SELECT board, scope, task_status FROM comms_messages "
        "WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None or row["task_status"] == "failed":
        return []
    board, scope = row["board"], row["scope"]
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET task_status='failed', failed_at=?, fail_reason=? "
            "WHERE id=?",
            (now, reason[:500], message_id),
        )
        conn.commit()

    all_pending = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' "
        "AND task_status IN ('pending','in_progress') AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()
    dep_index = {r["id"]: json.loads(r["depends_on"] or "[]") for r in all_pending}
    blocked: list[str] = []
    frontier: set[str] = {message_id}
    with _get_write_lock(conn):
        changed = True
        while changed:
            changed = False
            for tid, deps in list(dep_index.items()):
                if tid in blocked:
                    continue
                if frontier & set(deps):
                    conn.execute(
                        "UPDATE comms_messages SET task_status='blocked' WHERE id=?",
                        (tid,),
                    )
                    blocked.append(tid)
                    frontier.add(tid)
                    changed = True
        conn.commit()
    return blocked


def reclaim_stale_claims(conn: sqlite3.Connection, board: str, scope: str) -> list[str]:
    """On scheduler startup, revert in_progress tasks back to pending.

    Called once per run resume so orphaned in_progress rows (left by a
    crashed scheduler process) re-enter the frontier. Returns the IDs
    that were reverted.
    """
    rows = conn.execute(
        "SELECT id FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND task_status='in_progress' "
        "AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    with _get_write_lock(conn):
        conn.execute(
            f"UPDATE comms_messages SET task_status='pending', claimed_by=NULL "
            f"WHERE id IN ({ph})",
            ids,
        )
        conn.commit()
    return ids


def soft_delete_message(conn: sqlite3.Connection, message_id: str, force: bool = False) -> str:
    """Retract a message by soft-deleting it.

    By default a message is retractable only while no agent has read it (a human
    reading their own message does not lock it; any other reader does). Pass
    ``force=True`` to let the human remove ANY board message regardless of who has
    read it — used by the board UI so every message has a delete option. The
    delete is soft (``status='trashed'``), so it stays recoverable from trash.

    Returns one of: ``"deleted"`` · ``"locked"`` (read-locked, force not set) ·
    ``"not_found"``.
    """
    row = conn.execute(
        "SELECT read_by FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    try:
        read_by = json.loads(row["read_by"] or "[]")
    except (json.JSONDecodeError, TypeError):
        read_by = []
    if not force and any(reader not in ("human", "you") for reader in read_by):
        return "locked"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET deleted_at=?, status='trashed' WHERE id=?",
            (_now(), message_id),
        )
        conn.commit()
    return "deleted"
