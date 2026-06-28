"""Task DAG queries — comms_messages rows with type='task'."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock
from .comms_messages import _now


def get_ready_tasks(
    conn: sqlite3.Connection,
    boards: list[str],
    scopes: list[str],
    goal_id: str | None = None,
) -> list[dict]:
    """Return task messages where every depends_on ID has task_status='done'.

    When goal_id is given, the frontier is scoped to that goal's tasks only.
    """
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
    """Set task_status='done'. Returns list of message IDs that became newly ready.

    Idempotent: completing an already-done task returns [] with no DB write.
    """
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
    """Atomically transition pending → in_progress. Returns True if this caller won."""
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

    Returns the list of blocked dependent IDs. Idempotent.
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

    Called once per run resume so orphaned in_progress rows re-enter the frontier.
    Returns the IDs that were reverted.
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
