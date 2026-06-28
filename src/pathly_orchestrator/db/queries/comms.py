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
    context_refs: list[dict] | None = None,
) -> str:
    """Insert a new message into comms_messages. Returns the new message_id.

    goal_id ties a task to its goal message; executor ('single'|'loop'|'team')
    is set on the goal message only. Both default to None so existing callers
    keep their behavior (the columns are harmlessly NULL).
    context_refs is a JSON-encoded list of {artifact, anchor?} advisory links
    (Phase 2 — shape guard only; resolve-against-index gate lands in Phase 3).
    """
    message_id = str(uuid.uuid4())
    # A task enters the DAG frontier as 'pending' so get_ready_tasks() (which
    # filters task_status='pending') can pick it up. Non-task messages leave it NULL.
    task_status = "pending" if type == "task" else None
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_messages "
            "(id, board, scope, from_agent, to_agent, type, text, options, reply_to, stage, conv, ts, depends_on, task_status, artifact_path, artifact_type, goal_id, executor, context_refs) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                json.dumps(context_refs) if context_refs is not None else None,
            ),
        )
        conn.commit()
    return message_id


def set_goal_executor(conn: sqlite3.Connection, message_id: str, executor: str) -> None:
    """Persist the chosen executor on a goal message (UI selector override).

    Lets the board reflect the user's pick after a reload — the dispatcher reads
    executor from the goal row, so persisting keeps that authoritative."""
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET executor=? WHERE id=? AND type='goal'",
            (executor, message_id),
        )
        conn.commit()


def get_messages(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    type: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return messages for the given board/scope, newest first."""
    sql = (
        "SELECT * FROM comms_messages WHERE board=? AND scope=? AND deleted_at IS NULL"
    )
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


def _dist_of(row: dict) -> float:
    """Cosine distance of a search row, or a large sentinel when it carries no semantic score."""
    d = row.get("_distance")
    return d if d is not None else 9e9


def search_by_embedding(
    conn: sqlite3.Connection,
    embedding: list[float],
    boards: list[str],
    scopes: list[str],
    k: int = 6,
) -> list[dict]:
    """Return up to k messages ordered by semantic similarity (or recency when vec unavailable).

    Merges two vector channels and dedups by message (each artifact appears once, ranked by its
    BEST match): the PARENT vector (whole summary/message, in comms_embeddings) and the CHILD
    chunk vectors (per-bullet / per-section, in comms_chunk_embeddings) — so a query matching one
    subtopic of a multi-topic artifact still retrieves it. Messages with no chunks rank by their
    parent vector exactly as before.
    """
    if not boards or not scopes:
        return []
    if _VEC_AVAILABLE:
        board_ph = ",".join("?" * len(boards))
        scope_ph = ",".join("?" * len(scopes))
        import struct

        embedding_bytes = struct.pack(f"{len(embedding)}f", *embedding)
        base: list[Any] = [embedding_bytes] + list(boards) + list(scopes)
        # `_distance` is the raw cosine distance (aliased for ORDER BY + caller thresholding).
        # PARENT vectors: one whole-summary/message vector each (the existing channel).
        parent_sql = (
            "SELECT m.*, vec_distance_cosine(e.embedding, ?) AS _distance "  # nosec B608
            "FROM comms_messages m JOIN comms_embeddings e ON e.message_id = m.id "
            f"WHERE m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
            "AND m.deleted_at IS NULL ORDER BY _distance ASC LIMIT ?"
        )
        best: dict[str, dict] = {}
        for r in conn.execute(parent_sql, base + [k * 2]).fetchall():
            best[r["id"]] = dict(r)
        # CHILD vectors: per-chunk recall on multi-topic artifacts; dedup by message, keep the
        # nearest of (parent, any chunk). Guarded so an older DB without the table still works.
        try:
            child_sql = (
                "SELECT m.*, vec_distance_cosine(c.embedding, ?) AS _distance, "  # nosec B608
                "c.chunk_text AS _matched_chunk "
                "FROM comms_messages m JOIN comms_chunk_embeddings c ON c.message_id = m.id "
                f"WHERE m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
                "AND m.deleted_at IS NULL ORDER BY _distance ASC LIMIT ?"
            )
            for r in conn.execute(child_sql, base + [k * 3]).fetchall():
                d = dict(r)
                prev = best.get(d["id"])
                if prev is None or _dist_of(d) < _dist_of(prev):
                    best[d["id"]] = d
        except sqlite3.OperationalError:
            pass  # chunk table absent (older DB) → parents only
        return sorted(best.values(), key=_dist_of)[:k]

    board_ph = ",".join("?" * len(boards))
    scope_ph = ",".join("?" * len(scopes))
    sql = (
        "SELECT * FROM comms_messages "  # nosec B608
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        "AND deleted_at IS NULL "
        "ORDER BY ts DESC LIMIT ?"
    )
    params = list(boards) + list(scopes) + [k]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


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
        "SELECT m.* FROM comms_messages m "  # nosec B608
        "JOIN comms_fts ON comms_fts.rowid = m.rowid "
        f"WHERE comms_fts MATCH ? AND m.board IN ({board_ph}) AND m.scope IN ({scope_ph}) "
        "AND m.deleted_at IS NULL "
        "ORDER BY rank LIMIT ?"
    )
    try:
        rows = conn.execute(
            sql, [query_text] + list(boards) + list(scopes) + [k]
        ).fetchall()
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
    bm25_rows = (
        search_by_keyword(conn, query_text, boards, scopes, k * 2) if query_text else []
    )
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
    # Carry the raw cosine distance through so a caller can threshold weak semantic
    # hits (RRF fuses ranks, not scores, so the raw distance must ride along).
    sem_dist = {row["id"]: row.get("_distance") for row in sem_rows}
    out: list[dict] = []
    for r in ranked[:k]:
        row = dict(r["row"])
        if row.get("id") in sem_dist:
            row["_distance"] = sem_dist[row["id"]]
        out.append(row)
    return out


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
        "SELECT * FROM comms_messages "  # nosec B608
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
        (old_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    if row["superseded_by"]:
        return "already_superseded"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET superseded_by=? WHERE id=?", (new_id, old_id)
        )
        conn.commit()
    return "ok"


# Types that carry structure or governance — NEVER auto-deduped (superseding a task
# breaks the DAG; a goal breaks runs; a decision/escalation/question is governance the
# human supersedes deliberately). Dedup only collapses free-form notes.
_DEDUP_PROTECTED_TYPES = (
    "goal",
    "task",
    "decision",
    "escalation",
    "question",
    "answer",
)


def dedupe_board(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    *,
    max_distance: float = 0.08,
    embed_fn=None,
) -> list[dict]:
    """Supersede near-duplicate free-form notes on a board, keeping the newest of each
    near-identical cluster (deterministic consolidation — no LLM).

    For each non-superseded note (newest first) we find its semantic neighbours and
    supersede any OLDER note within ``max_distance`` (cosine; 0.08 ≈ near-identical) by it.
    Structural/governance types (:data:`_DEDUP_PROTECTED_TYPES`) are never touched, so the
    task-DAG and decisions are safe. Returns the list of
    ``{"superseded", "by", "distance"}`` pairs applied. No-op (returns []) when embeddings
    are unavailable. Idempotent: a second run finds nothing new.
    """
    if embed_fn is None:
        try:
            from pathly_orchestrator.runner.embeddings import embed as embed_fn  # type: ignore
        except Exception:
            return []

    placeholders = ",".join("?" * len(_DEDUP_PROTECTED_TYPES))
    rows = conn.execute(
        "SELECT id, ts, text FROM comms_messages "  # nosec B608
        "WHERE board=? AND scope=? AND deleted_at IS NULL "
        "AND (superseded_by IS NULL OR superseded_by='') "
        f"AND type NOT IN ({placeholders}) "
        "ORDER BY ts DESC",
        [board, scope, *_DEDUP_PROTECTED_TYPES],
    ).fetchall()

    superseded: set[str] = set()
    pairs: list[dict] = []
    for r in rows:
        keeper_id, keeper_ts = r["id"], r["ts"]
        if keeper_id in superseded:
            continue
        try:
            emb = embed_fn(r["text"] or "")
        except Exception:
            emb = None
        if emb is None:
            continue
        neighbours = search_by_embedding(conn, emb, [board], [scope], k=20)
        for n in neighbours:
            nid = n.get("id")
            if not nid or nid == keeper_id or nid in superseded:
                continue
            dist = n.get("_distance")
            if dist is None or dist > max_distance:
                continue
            # Keep the newer; supersede only strictly-older near-duplicates.
            if (n.get("ts") or "") >= keeper_ts:
                continue
            if supersede_message(conn, nid, keeper_id) == "ok":
                superseded.add(nid)
                pairs.append({"superseded": nid, "by": keeper_id, "distance": dist})
    return pairs


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
        "SELECT * FROM comms_messages "  # nosec B608
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


def store_chunk_embeddings(
    conn: sqlite3.Connection,
    message_id: str,
    chunks: list[tuple[str, list[float]]],
) -> None:
    """Replace the child-chunk embeddings for *message_id* (re-summarize replaces them).

    ``chunks`` is ``[(chunk_text, vector), …]`` — one per summary bullet/section. Always clears
    the message's existing chunks first so stale ones from a previous (longer) summary can't
    linger. No-op when vec is unavailable (vec_distance_cosine would be missing at search time).
    """
    if not _VEC_AVAILABLE:
        return
    import struct

    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM comms_chunk_embeddings WHERE message_id=?", (message_id,)
        )
        for i, (text, vector) in enumerate(chunks):
            eb = struct.pack(f"{len(vector)}f", *vector)
            conn.execute(
                "INSERT OR REPLACE INTO comms_chunk_embeddings "
                "(chunk_id, message_id, embedding, chunk_text) VALUES (?, ?, ?, ?)",
                (f"{message_id}:{i + 1}", message_id, eb, text),
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
            f"UPDATE comms_messages SET deleted_at=NULL, status='pending' WHERE id IN ({ph})",  # nosec B608
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
        "SELECT * FROM comms_messages "  # nosec B608
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        f"AND type='task' AND task_status='pending' AND deleted_at IS NULL{goal_clause}"
    )
    pending_rows = conn.execute(
        pending_sql, list(boards) + list(scopes) + goal_param
    ).fetchall()

    done_sql = (
        "SELECT id FROM comms_messages "  # nosec B608
        f"WHERE board IN ({board_ph}) AND scope IN ({scope_ph}) "
        f"AND type='task' AND task_status='done' AND deleted_at IS NULL{goal_clause}"
    )
    done_ids = {
        r["id"]
        for r in conn.execute(
            done_sql, list(boards) + list(scopes) + goal_param
        ).fetchall()
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
            "UPDATE comms_messages SET task_status='done', completed_at=? WHERE id=?",
            (_now(), message_id),
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
            f"UPDATE comms_messages SET task_status='pending', claimed_by=NULL "  # nosec B608
            f"WHERE id IN ({ph})",
            ids,
        )
        conn.commit()
    return ids


def soft_delete_message(
    conn: sqlite3.Connection, message_id: str, force: bool = False
) -> str:
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


def reindex_artifact_sections(
    conn: sqlite3.Connection,
    artifact_id: str,
    sections: list[dict],
    mtime: float,
    content_hash: str,
    structure_key: str,
) -> None:
    """Replace all section rows for artifact_id and stamp staleness fingerprints.

    Idempotent: DELETE then INSERT under the write lock (mirrors store_embedding's
    locking pattern). Does NOT re-summarize or re-embed — the expensive tier fires
    async only on structure_key change (§3.4). sections is a list of dicts with keys:
    id, anchor, heading, line_start, line_end, ordinal.
    """
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
    """Update only indexed_mtime for artifact_id (mtime moved, content unchanged).

    Used when cur_hash == stored_hash: avoids wiping the section index while
    still recording the new mtime so the next staleness check is a fast no-op.
    """
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
    """Resolve a comms_artifacts row by (scope via owning message, path).

    Returns the existing artifact dict if found. For legacy plans (file on disk but
    never posted as type='artifact'), creates a minimal sentinel row so the hydration
    endpoint never crashes (§6 row 2d). Returns None only when the path does not
    exist on disk and no row exists.
    """
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

    # Defense-in-depth: refuse to create a sentinel for any path that does not
    # contain a /pathly/plans/ segment — blocks the by-id disclosure vector even
    # if a poisoned path somehow reached this function.
    normalized_path = path.replace("\\", "/")
    if "/pathly/plans/" not in normalized_path:
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
    """Board Catalog query (§5a.4): deterministic listing of artifacts for a scope.

    Returns [{path, type, title, summary}] over exposed boards. board/scope live on
    comms_messages, joined via the artifact FK. Optional goal_id/order/limit/offset
    are the §5a.6 scaling params — omitted => flat listing unchanged.
    NULL summaries degrade to path/title (consumer responsibility per §7).
    """
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


def update_message_text(conn: sqlite3.Connection, message_id: str, text: str) -> str:
    """Edit a message's text in place — used by the board UI to rename a goal.

    The edit is in place so the message id is preserved and a goal keeps its task
    links (tasks reference the goal by id). Embeddings are not recomputed here;
    hybrid search reflects the new text on the next reindex.

    Returns ``"updated"`` or ``"not_found"``.
    """
    row = conn.execute(
        "SELECT id FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if row is None:
        return "not_found"
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET text=? WHERE id=?",
            (text, message_id),
        )
        conn.commit()
    return "updated"


def update_artifact_summary(
    conn: sqlite3.Connection,
    artifact_id: str,
    summary: str,
    token_count: int | None = None,
) -> None:
    """Overwrite comms_artifacts.summary (and optionally token_count) for artifact_id.

    The canonical summary writer. Called by the client writeback route
    (set_artifact_summary in comms_summary.py) after the renderer runs aiRouter.
    """
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


