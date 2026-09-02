"""Board message CRUD — comms_messages table write/read operations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from ..connection import _get_write_lock

# Goal-message field accessors live in comms_goal_fields (this file sits on the 400-line
# ratchet). Re-exported so `from ...comms_messages import set_message_slug` — which
# supervisor/slug.py, goal_executor.py and fsm_compose_paths.py all do — keeps working.
from .comms_goal_fields import (  # noqa: F401
    get_goal_board_scope,
    read_message_slug,
    set_goal_executor,
    set_message_slug,
)


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
    files: list[str] | None = None,
    lane: str | None = None,
    slug: str | None = None,
    run_id: str | None = None,
) -> str:
    """Insert a new message into comms_messages. Returns the new message_id.

    ``run_id`` (unified-control-plane) correlates this post to the run that made it, so the
    control plane's RunDetail Board tab shows a run's *exact* posts instead of a time-window guess.
    """
    message_id = str(uuid.uuid4())
    task_status = "pending" if type == "task" else None
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO comms_messages "
            "(id, board, scope, from_agent, to_agent, type, text, options, reply_to, stage, conv, ts, depends_on, task_status, artifact_path, artifact_type, goal_id, executor, context_refs, files, lane, slug, run_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                json.dumps(files) if files is not None else None,
                lane,
                slug,
                run_id,
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
    include_structural: bool = False,
) -> list[dict]:
    """Return messages for the given board/scope, newest first.

    ``include_structural``: when True (and no explicit ``type`` filter), goal + task rows are
    ALWAYS returned in full — they anchor the "Goals & Tasks" view and are bounded (a board has a
    handful of goals / a DAG of tasks), so ``limit`` applies only to the volatile chat/status
    stream. Without this, run churn (status/phase posts) evicts the OLDEST rows — the goals — out
    of the newest-``limit`` window, and every task then renders under "Ungrouped tasks". The
    Messages view already filters goal/task out of the thread, so full inclusion is invisible there.
    """
    where = "board=? AND scope=? AND deleted_at IS NULL"
    params: list[Any] = [board, scope]
    if type is not None:
        where += " AND type=?"
        params.append(type)
    if status is not None:
        where += " AND status=?"
        params.append(status)

    if not include_structural or type is not None:
        sql = f"SELECT * FROM comms_messages WHERE {where} ORDER BY ts DESC LIMIT ?"  # nosec B608
        return [dict(r) for r in conn.execute(sql, params + [limit]).fetchall()]

    # Structural-inclusive board feed: every goal/task + the newest `limit` of everything else.
    structural = conn.execute(
        f"SELECT * FROM comms_messages WHERE {where} AND type IN ('goal','task') "  # nosec B608
        "ORDER BY ts DESC",
        params,
    ).fetchall()
    others = conn.execute(
        f"SELECT * FROM comms_messages WHERE {where} AND type NOT IN ('goal','task') "  # nosec B608
        "ORDER BY ts DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    merged = [dict(r) for r in structural] + [dict(r) for r in others]
    merged.sort(key=lambda r: r.get("ts") or "", reverse=True)
    return merged


def get_all_messages(conn: sqlite3.Connection, board: str, scope: str) -> list[dict]:
    """Return EVERY non-deleted message for (board, scope) — no LIMIT, stable-sorted by
    (ts, id) ascending. Used by the board disk-mirror exporter, which must snapshot the
    entire live board (not a windowed feed) in a deterministic order for clean git diffs.
    """
    rows = conn.execute(
        "SELECT * FROM comms_messages WHERE board=? AND scope=? AND deleted_at IS NULL "
        "ORDER BY ts ASC, id ASC",
        (board, scope),
    ).fetchall()
    return [dict(r) for r in rows]


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
        # Persist the chosen option id AND mark the question 'answered' (the status the
        # board UI's question card reads) so the selection survives a board reload — the
        # 5s fallback poll used to revert it because neither round-tripped.
        conn.execute(
            "UPDATE comms_messages SET status='answered', answer_option=? WHERE id=?",
            (option_id, question_id),
        )
        conn.commit()
    return answer_id


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


def soft_delete_message(
    conn: sqlite3.Connection, message_id: str, force: bool = False
) -> str:
    """Retract a message by soft-deleting it.

    Returns one of: ``"deleted"`` · ``"locked"`` · ``"not_found"``.
    Pass ``force=True`` to remove ANY board message regardless of who has read it.
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


def update_message_text(conn: sqlite3.Connection, message_id: str, text: str) -> str:
    """Edit a message's text in place. Returns ``"updated"`` or ``"not_found"``."""
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


# insert_message_row lives in comms_hydrate.py (400-line cap); re-exported here.
from .comms_hydrate import insert_message_row  # noqa: E402, F401
