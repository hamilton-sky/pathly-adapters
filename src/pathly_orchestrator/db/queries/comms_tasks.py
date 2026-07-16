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


def get_tasks(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    *,
    task_status: str | None = None,
    goal_id: str | None = None,
    limit: int = 200,
) -> list[dict]:
    """List task messages, filtered by the DAG ``task_status`` column.

    The task lifecycle lives in ``task_status`` (pending/in_progress/done/failed/
    blocked) — NOT the generic message ``status`` column, which stays at its posted
    value ('pending') for a task's whole life. Listing tasks via ``status`` therefore
    returns completed tasks as if still pending; this helper filters the right column
    and optionally scopes to a single goal. Newest first.
    """
    sql = (
        "SELECT * FROM comms_messages "  # nosec B608
        "WHERE board=? AND scope=? AND type='task' AND deleted_at IS NULL"
    )
    params: list = [board, scope]
    if task_status is not None:
        sql += " AND task_status=?"
        params.append(task_status)
    if goal_id is not None:
        sql += " AND goal_id=?"
        params.append(goal_id)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(limit)
    return [dict(r) for r in conn.execute(sql, params).fetchall()]


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


def count_tasks_for_goal(conn: sqlite3.Connection, goal_id: str) -> int:
    """Count non-deleted task rows belonging to a goal (any task_status).

    Used by the on_board_count FSM gate to assert a goal's DAG was actually
    seeded before advancing (Fix B).
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE goal_id=? AND type='task' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    return int(row["n"]) if row else 0


def count_ready_tasks_for_goal(conn: sqlite3.Connection, goal_id: str) -> int:
    """Count a goal's BUILDABLE tasks: task_status='pending' with every dependency done.

    Drives the team-build per-task loop — REVIEWING routes back to BUILDING while this is > 0
    (one more task to build+review) and falls through to TESTING once it reaches 0 (DAG drained).
    Goal-scoped mirror of ``get_ready_tasks``' readiness rule.
    """
    pending = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE goal_id=? AND type='task' AND task_status='pending' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchall()
    done_ids = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM comms_messages "
            "WHERE goal_id=? AND type='task' AND task_status='done' AND deleted_at IS NULL",
            (goal_id,),
        ).fetchall()
    }
    n = 0
    for r in pending:
        deps = json.loads(r["depends_on"] or "[]")
        if all(dep in done_ids for dep in deps):
            n += 1
    return n


def count_incomplete_tasks_for_goal(conn: sqlite3.Connection, goal_id: str) -> int:
    """Count a goal's tasks that are NOT done (pending / in_progress / failed / blocked / NULL).

    Drives the ``require_tasks_done`` gate on TESTING->RETRO: a goal must not finish (reach RETRO)
    while any of its tasks are unfinished or failed. ``IS NOT 'done'`` so NULL task_status counts
    as incomplete.
    """
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE goal_id=? AND type='task' AND task_status IS NOT 'done' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchone()
    return int(row["n"]) if row else 0


def count_ready_tasks_for_scope(
    conn: sqlite3.Connection, board: str, scope: str
) -> int:
    """Feature-scoped mirror of ``count_ready_tasks_for_goal``: BUILDABLE tasks (pending with
    every dependency done) across ALL goals in a ``(board, scope)``. This is the frontier
    ``team/build`` fetches by feature+scope, so the linear team pipeline's REVIEWING loop counts
    the whole feature rather than a single goal."""
    pending = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND task_status='pending' AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()
    done_ids = {
        r["id"]
        for r in conn.execute(
            "SELECT id FROM comms_messages "
            "WHERE board=? AND scope=? AND type='task' AND task_status='done' AND deleted_at IS NULL",
            (board, scope),
        ).fetchall()
    }
    n = 0
    for r in pending:
        deps = json.loads(r["depends_on"] or "[]")
        if all(dep in done_ids for dep in deps):
            n += 1
    return n


def count_incomplete_tasks_for_scope(
    conn: sqlite3.Connection, board: str, scope: str
) -> int:
    """Feature-scoped mirror of ``count_incomplete_tasks_for_goal``: tasks NOT done across ALL
    goals in a ``(board, scope)``. Drives the linear team pipeline's REVIEWING->TESTING
    completeness gate."""
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND task_status IS NOT 'done' AND deleted_at IS NULL",
        (board, scope),
    ).fetchone()
    return int(row["n"]) if row else 0


def goal_refs_coverage(conn: sqlite3.Connection, goal_id: str) -> dict:
    """Per-goal context_refs coverage: how many of a goal's tasks carry ≥1 ref (T3c).

    Surfaces the ISSUE-4 gap — tasks with no context_refs fall back to weaker
    (auto-derived/semantic) context — so a human can see it BEFORE dispatching a goal.
    Counts non-deleted type='task' rows for the goal; a task counts as covered when
    context_refs is a non-empty JSON array.
    """
    rows = conn.execute(
        "SELECT context_refs FROM comms_messages "
        "WHERE goal_id=? AND type='task' AND deleted_at IS NULL",
        (goal_id,),
    ).fetchall()
    total = len(rows)
    with_refs = 0
    for r in rows:
        raw = r["context_refs"]
        if not raw:
            continue
        try:
            refs = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            refs = None
        if isinstance(refs, list) and len(refs) > 0:
            with_refs += 1
    return {
        "goal_id": goal_id,
        "total": total,
        "with_refs": with_refs,
        "without_refs": total - with_refs,
        "coverage_pct": round(100.0 * with_refs / total, 1) if total else None,
    }


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


def feature_task_files(
    conn: sqlite3.Connection, scope: str, goal_id: str | None = None
) -> set[str]:
    """Union of declared ``files`` across a feature's non-terminal tasks (pending/in_progress).

    Empty when nothing was declared — the caller treats that as "touches everything"
    (conservative serialize) via the file-claims WILDCARD.
    """
    sql = (
        "SELECT files FROM comms_messages WHERE board='feature' AND scope=? "
        "AND type='task' AND task_status IN ('pending','in_progress') AND deleted_at IS NULL"
    )
    params: list = [scope]
    if goal_id is not None:
        sql += " AND goal_id=?"
        params.append(goal_id)
    out: set[str] = set()
    for r in conn.execute(sql, params).fetchall():
        try:
            for f in json.loads(r["files"] or "[]"):
                if str(f).strip():
                    out.add(str(f).strip())
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def get_active_file_claims(
    conn: sqlite3.Connection, exclude_scope: str | None = None
) -> dict[str, list[str]]:
    """``{scope: [files]}`` declared by OTHER features' active (pending/in_progress) tasks.

    Feeds the planner-awareness view — what files sibling features intend to touch, so a
    planner can design its DAG to avoid overlap.
    """
    rows = conn.execute(
        "SELECT scope, files FROM comms_messages WHERE board='feature' AND type='task' "
        "AND task_status IN ('pending','in_progress') AND deleted_at IS NULL "
        "AND files IS NOT NULL"
    ).fetchall()
    claims: dict[str, set[str]] = {}
    for r in rows:
        s = r["scope"]
        if not s or s == exclude_scope:
            continue
        try:
            fs = [
                str(f).strip() for f in json.loads(r["files"] or "[]") if str(f).strip()
            ]
        except (json.JSONDecodeError, TypeError):
            fs = []
        if fs:
            claims.setdefault(s, set()).update(fs)
    return {s: sorted(fs) for s, fs in claims.items()}
