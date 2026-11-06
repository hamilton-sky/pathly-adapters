"""Routed questions: who answers a board question a running agent addressed to a role.

A ``question`` whose ``to_agent`` is one of ``CONSULT_ROLES`` is answered by a one-shot consult
run of that role (chief-autopilot-round-two). ``route_decision`` says whether it is routed
(``route``), handed to the person (``person``, with the reason: an unknown role, the per-task
limit ``consult.max_per_task`` or the goal's consult cost line ``consult.goal_cost_usd``) or left
alone (``none``: questions to ``human`` or ``*`` are round one's park, a consult never consults).
``consult_routes`` (``migrations_consult``) keeps one row per routed or handed-on question.

Handing a question to the person re-addresses the same row (``to_agent='human'``), so a task
parked on it still names it, and a system ``status`` reply records who handed it on and why (a
``status`` row never frees a task: only ``type: answer`` does).

``db/`` only: it imports nothing above ``db/``. Every SQL here is one literal.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import time
from dataclasses import dataclass

from ..connection import _get_write_lock
from ..provenance_values import SYSTEM_AUTHOR
from .app_settings import get_setting
from .comms_messages import post_message

CONSULT_ROLES = ("architect", "designer", "po", "planner", "tester", "reviewer")

STATUSES = frozenset(
    {"queued", "running", "answered", "to_person", "withheld", "failed"}
)
END_STATUSES = frozenset({"answered", "to_person", "withheld", "failed"})

CONSULT_RUN_PREFIX = "consult-"
DEFAULT_MAX_PER_TASK = 3
DEFAULT_GOAL_COST_USD = 2.0
# How much of an agent-written ``to_agent`` (or a caller's reason) is echoed into a route row or a
# system-stamped reply: one line, capped, so an agent cannot write a forged block of text there.
ROLE_ECHO_MAX = 40
WHY_MAX = 300

# The loop scheduler's run id, ``sched-<task>#<attempt>`` (same pattern as
# ``supervisor/task_proof._RUN_ID``; copied, since ``db/`` may not import ``supervisor/``).
_SCHED_RUN_ID = re.compile(r"sched-(?P<task>[^#]+)#[0-9]+")


def _one_line(text: str | None, limit: int) -> str:
    """``text`` as one printable line (every whitespace run one space), at most ``limit`` chars."""
    line = " ".join(str(text or "").split())
    return "".join(ch for ch in line if ch.isprintable())[:limit]


@dataclass(frozen=True)
class Decision:
    """What to do with one question: ``kind`` is ``route``, ``person`` or ``none``."""

    kind: str
    reason: str = ""
    role: str | None = None
    task_id: str | None = None
    goal_key: str | None = None
    asking_run_id: str | None = None


def consult_limits(conn: sqlite3.Connection) -> tuple[int, float]:
    """``(max_per_task, goal_cost_usd)`` from the settings; a missing, non-numeric or negative
    value gives the default (3 and 2.0). ``goal_cost_usd`` 0 routes nothing."""
    raw_max = get_setting(conn, "consult.max_per_task", None)
    raw_cost = get_setting(conn, "consult.goal_cost_usd", None)
    try:
        max_per_task = int(raw_max) if raw_max else DEFAULT_MAX_PER_TASK
    except (TypeError, ValueError):
        max_per_task = DEFAULT_MAX_PER_TASK
    if max_per_task < 0:
        max_per_task = DEFAULT_MAX_PER_TASK
    try:
        cost = float(raw_cost) if raw_cost else DEFAULT_GOAL_COST_USD
    except (TypeError, ValueError):
        cost = DEFAULT_GOAL_COST_USD
    if not math.isfinite(cost) or cost < 0:
        cost = DEFAULT_GOAL_COST_USD
    return max_per_task, cost


def asking_task(conn: sqlite3.Connection, run_id: str | None) -> dict | None:
    """The task a run works on: ``<task>`` of ``sched-<task>#<n>``, else the ``in_progress`` task
    the run claimed (the newest claim when there are several). None for no run or no task.
    """
    if not run_id:
        return None
    found = _SCHED_RUN_ID.fullmatch(run_id)
    if found:
        row = conn.execute(
            "SELECT * FROM comms_messages WHERE id=? AND type='task' "
            "AND deleted_at IS NULL",
            (found.group("task"),),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM comms_messages WHERE type='task' AND task_status='in_progress' "
            "AND claimed_by=? AND deleted_at IS NULL "
            "ORDER BY claimed_at DESC, ts DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    return dict(row) if row is not None else None


def goal_key(task: dict | None, run_id: str | None) -> str | None:
    """A question's goal key: its asking task's ``goal_id``, else the asking run id."""
    if task and task.get("goal_id"):
        return str(task["goal_id"])
    return run_id


def _routed_count(conn: sqlite3.Connection, task_id: str | None, run_id: str) -> int:
    """Routes that count against a task (or, with no task, the asking run): every status but
    ``to_person``."""
    if task_id:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM consult_routes "
            "WHERE task_id=? AND status != 'to_person'",
            (task_id,),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM consult_routes "
            "WHERE task_id IS NULL AND asking_run_id=? AND status != 'to_person'",
            (run_id,),
        ).fetchone()
    return int(row["n"] or 0)


def _is_routed(conn: sqlite3.Connection, question_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM consult_routes WHERE question_id=?", (question_id,)
    ).fetchone()
    return row is not None


def route_decision(conn: sqlite3.Connection, question_id: str) -> Decision:
    """Who answers ``question_id``: a consult run (``route``), the person (``person``) or
    nothing here (``none``)."""
    q = conn.execute(
        "SELECT to_agent, author_run_id FROM comms_messages "
        "WHERE id=? AND type='question' AND deleted_at IS NULL",
        (question_id,),
    ).fetchone()
    if q is None:
        return Decision("none", "not a live question")
    run_id = q["author_run_id"]
    if not run_id:
        return Decision("none", "no asking run")
    to = _one_line((q["to_agent"] or "*").lower(), ROLE_ECHO_MAX)
    if to in ("human", "*"):
        return Decision("none", "a question to the person")
    if run_id.startswith(CONSULT_RUN_PREFIX):
        return Decision("none", "a consult run's own question")
    if _is_routed(conn, question_id):
        return Decision("none", "already routed")
    task = asking_task(conn, run_id)
    task_id = task["id"] if task else None
    key = goal_key(task, run_id)
    fields = {"role": to, "task_id": task_id, "goal_key": key, "asking_run_id": run_id}
    if to not in CONSULT_ROLES:
        return Decision("person", f"unknown role {to}", **fields)
    max_per_task, line = consult_limits(conn)
    if _routed_count(conn, task_id, run_id) >= max_per_task:
        reason = f"routed question limit ({max_per_task}) reached for task {task_id or run_id}"
        return Decision("person", reason, **fields)
    if line == 0 or goal_consult_cost(conn, key) >= line:
        return Decision(
            "person", f"consult cost line ${line:.2f} reached for {key}", **fields
        )
    return Decision("route", "", **fields)


def record_route(
    conn: sqlite3.Connection,
    decision: Decision,
    question_id: str,
    status: str = "queued",
) -> bool:
    """Insert the route row for ``question_id`` once; True when this call inserted it.

    A ``route`` decision is counted again inside the insert: when the asking task (or taskless
    run) already holds ``consult.max_per_task`` routes not ``to_person``, nothing is inserted and
    the call returns False, so questions decided at the same moment cannot pass the cap
    (``route_decision`` then says ``person`` with the limit reason)."""
    if status not in STATUSES:
        raise ValueError(f"unknown consult route status {status!r}")
    now = time.time()
    with _get_write_lock(conn):
        cap = None
        if decision.kind == "route" and status != "to_person":
            cap = consult_limits(conn)[0]
        cur = conn.execute(
            "INSERT OR IGNORE INTO consult_routes "
            "(question_id, role, task_id, goal_key, asking_run_id, status, reason, "
            "created_at, ended_at) "
            "SELECT :qid, :role, :task, :goal, :run, :status, :reason, :now, :ended "
            "WHERE :cap IS NULL OR (SELECT COUNT(*) FROM consult_routes "
            "WHERE status != 'to_person' AND ((:task IS NOT NULL AND task_id = :task) "
            "OR (:task IS NULL AND task_id IS NULL AND asking_run_id = :run))) < :cap",
            {
                "qid": question_id,
                "role": decision.role or "",
                "task": decision.task_id,
                "goal": decision.goal_key,
                "run": decision.asking_run_id,
                "status": status,
                "reason": decision.reason or None,
                "now": now,
                "ended": now if status in END_STATUSES else None,
                "cap": cap,
            },
        )
        conn.commit()
    return cur.rowcount == 1


def set_route_status(
    conn: sqlite3.Connection,
    question_id: str,
    status: str,
    *,
    consult_run_id: str | None = None,
    reason: str | None = None,
) -> bool:
    """Set a route's status (and its consult run or reason when given); an end status sets
    ``ended_at``. True when a route row was changed."""
    if status not in STATUSES:
        raise ValueError(f"unknown consult route status {status!r}")
    ended = time.time() if status in END_STATUSES else None
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE consult_routes SET status=?, "
            "consult_run_id=COALESCE(?, consult_run_id), reason=COALESCE(?, reason), "
            "ended_at=COALESCE(?, ended_at) WHERE question_id=?",
            (status, consult_run_id, reason, ended, question_id),
        )
        conn.commit()
    return cur.rowcount == 1


def hand_to_person(
    conn: sqlite3.Connection, question_id: str, why: str, *, by: str
) -> bool:
    """Hand ``question_id`` to the person: the same row re-addressed ``to_agent='human'``, its
    route ``to_person`` with ``why`` (inserted when none exists), then a system ``status`` reply
    ``<by> handed this question to the person: <why>`` (``by`` and ``why`` made one capped line).
    A route that already ended (``answered``, ``failed``, ``withheld``) keeps its status and
    reason. False, and nothing changed, when the question does not exist or is deleted.
    """
    why = _one_line(why, WHY_MAX)
    by = _one_line(by, ROLE_ECHO_MAX)
    q = conn.execute(
        "SELECT board, scope, to_agent, author_run_id FROM comms_messages "
        "WHERE id=? AND type='question' AND deleted_at IS NULL",
        (question_id,),
    ).fetchone()
    if q is None:
        return False
    run_id = q["author_run_id"]
    task = asking_task(conn, run_id)
    now = time.time()
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET to_agent='human' WHERE id=?", (question_id,)
        )
        conn.execute(
            "INSERT INTO consult_routes "
            "(question_id, role, task_id, goal_key, asking_run_id, status, reason, "
            "created_at, ended_at) VALUES (?, ?, ?, ?, ?, 'to_person', ?, ?, ?) "
            "ON CONFLICT(question_id) DO UPDATE SET status='to_person', "
            "reason=excluded.reason, ended_at=excluded.ended_at "
            "WHERE consult_routes.status IN ('queued', 'running')",
            (
                question_id,
                _one_line((q["to_agent"] or "").lower(), ROLE_ECHO_MAX),
                task["id"] if task else None,
                goal_key(task, run_id),
                run_id,
                why,
                now,
                now,
            ),
        )
        conn.commit()
    post_message(
        conn,
        q["board"],
        q["scope"],
        "system",
        type="status",
        text=f"{by} handed this question to the person: {why}",
        reply_to=question_id,
        **SYSTEM_AUTHOR,
    )
    return True


def routes_for_questions(conn: sqlite3.Connection, ids: list[str]) -> list[dict]:
    """The route rows of ``ids`` (those that have one), oldest first."""
    if not ids:
        return []
    rows = conn.execute(
        "SELECT * FROM consult_routes "
        "WHERE question_id IN (SELECT value FROM json_each(?)) "
        "ORDER BY created_at ASC, question_id ASC",
        (json.dumps(list(ids)),),
    ).fetchall()
    return [dict(r) for r in rows]


def pending_routes(conn: sqlite3.Connection, ids: list[str]) -> list[str]:
    """The ids among ``ids`` whose route is ``queued`` or ``running``."""
    if not ids:
        return []
    rows = conn.execute(
        "SELECT question_id FROM consult_routes "
        "WHERE question_id IN (SELECT value FROM json_each(?)) "
        "AND status IN ('queued', 'running') "
        "ORDER BY created_at ASC, question_id ASC",
        (json.dumps(list(ids)),),
    ).fetchall()
    return [r["question_id"] for r in rows]


def goal_consult_cost(conn: sqlite3.Connection, goal_key: str | None) -> float:
    """The summed ``agent_invocations.cost_usd`` of the consult runs of ``goal_key``."""
    if not goal_key:
        return 0.0
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0) AS total FROM agent_invocations "
        "WHERE run_id IN (SELECT consult_run_id FROM consult_routes "
        "WHERE goal_key=? AND consult_run_id IS NOT NULL)",
        (goal_key,),
    ).fetchone()
    return float(row["total"] or 0.0)


def end_stale_routes(conn: sqlite3.Connection) -> list[str]:
    """Hand every ``queued`` or ``running`` route to the person with reason ``server restart``
    (no consult run survives a restart). Returns the question ids handed on."""
    rows = conn.execute(
        "SELECT question_id FROM consult_routes WHERE status IN ('queued', 'running') "
        "ORDER BY created_at ASC, question_id ASC"
    ).fetchall()
    handed: list[str] = []
    for row in rows:
        qid = row["question_id"]
        if not hand_to_person(conn, qid, "server restart", by="the server"):
            # The question row is gone or deleted: end the route all the same.
            set_route_status(conn, qid, "to_person", reason="server restart")
        handed.append(qid)
    return handed
