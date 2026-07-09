"""Goals read-model — goals enriched with their task-DAG rollup.

A pure-read query helper backing ``GET /comms/goals``: the symmetric READ partner
to the ``/comms/goals/{run,stop,decompose}`` write side. It saves callers (Studio,
agents, external tools) from the fetch-goals-then-fetch-tasks-and-join dance —
one call returns each goal + a `{total, done, in_progress, blocked, failed, ready}`
task rollup.

Part of the read-model split peeling reads off ``comms_messages`` into dedicated
query modules (see ``comms_counts`` for the FSM-gate counters). Never writes.
"""

from __future__ import annotations

import sqlite3

from .comms_tasks import count_ready_tasks_for_goal


def get_latest_goal_id(conn: sqlite3.Connection, board: str, scope: str) -> str | None:
    """Return the id of the most-recent active goal on ``(board, scope)``, or None.

    The FSM uses this to resolve a feature-scoped team run's goal for the board-count and
    task-completeness gates (``on_board_count`` / ``require_tasks_done``) when the caller did not
    pass a ``goal_id`` explicitly (Studio-Start and interactive ``/pathly team``). The team
    pipeline seeds exactly one goal per feature (plan.md Step 6); if several exist, the newest is
    this run's. Returns None when the feature has no goal (offline / non-team flows) — the gates
    then skip, unchanged.
    """
    row = conn.execute(
        "SELECT id FROM comms_messages "
        "WHERE board=? AND scope=? AND type='goal' AND deleted_at IS NULL "
        "ORDER BY ts DESC LIMIT 1",
        (board, scope),
    ).fetchone()
    return row["id"] if row else None


def get_goals_with_rollup(
    conn: sqlite3.Connection, board: str, scope: str
) -> list[dict]:
    """Return the goals on ``(board, scope)``, each with its task-DAG rollup.

    Each item carries the goal's core fields (id, slug, text, executor, from_agent,
    ts) plus ``tasks``: counts keyed by DAG ``task_status`` — ``total``, ``done``,
    ``in_progress``, ``pending``, ``blocked``, ``failed`` — and ``ready`` (the
    buildable frontier: pending tasks whose every dependency is ``done``). Goals are
    returned oldest-first, matching the board feed's natural order.
    """
    goals = conn.execute(
        "SELECT id, slug, text, executor, from_agent, ts FROM comms_messages "
        "WHERE board=? AND scope=? AND type='goal' AND deleted_at IS NULL "
        "ORDER BY ts ASC",
        (board, scope),
    ).fetchall()

    out: list[dict] = []
    for g in goals:
        gid = g["id"]
        by_status = {
            r["task_status"]: int(r["n"])
            for r in conn.execute(
                "SELECT task_status, COUNT(*) AS n FROM comms_messages "
                "WHERE goal_id=? AND type='task' AND deleted_at IS NULL "
                "GROUP BY task_status",
                (gid,),
            ).fetchall()
        }
        out.append(
            {
                "id": gid,
                "slug": g["slug"],
                "text": g["text"],
                "executor": g["executor"],
                "from_agent": g["from_agent"],
                "ts": g["ts"],
                "tasks": {
                    "total": sum(by_status.values()),
                    "done": by_status.get("done", 0),
                    "in_progress": by_status.get("in_progress", 0),
                    "pending": by_status.get("pending", 0),
                    "blocked": by_status.get("blocked", 0),
                    "failed": by_status.get("failed", 0),
                    # Dynamic frontier — pending with all deps done (reuses the DAG
                    # readiness rule so it never drifts from the scheduler's view).
                    "ready": count_ready_tasks_for_goal(conn, gid),
                },
            }
        )
    return out
