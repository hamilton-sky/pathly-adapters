"""Tasks that wait on a question: park a task on its run's open questions, free it on an answer.

A board or single run that posted a ``question`` to ``human`` (or ``*``) and ended with its task
still ``in_progress`` parks the task instead of failing it (chief-autopilot 06, spike S5):
``task_status='blocked'``, ``fail_reason='waiting_for_answer:<id>[,<id>]'`` and ``waits + 1``.
``attempts`` is left alone (the loop scheduler builds run ids from it, so it only grows); every
attempt limit compares ``attempts - waits``. An answer (``answer_question`` or a ``type: answer``
post with ``reply_to``) frees every task whose questions are then all answered: back to
``pending``, the reason cleared, the question ids kept in ``answered_questions`` (a JSON list)
for the next attempt. Questions to a role (``to: architect``) never park a task.

Shared with the loop scheduler (ticket 12). Every SQL here is one literal.
"""

from __future__ import annotations

import json
import logging
import sqlite3

from ..connection import _get_write_lock

logger = logging.getLogger("pathly.task_waits")

WAITING_FOR_ANSWER = "waiting_for_answer"
_PREFIX = WAITING_FOR_ANSWER + ":"


def open_questions_by_run(conn: sqlite3.Connection, run_id: str) -> list[str]:
    """Ids of the run's unanswered questions to ``human`` or ``*``, oldest first.

    The run is the question's ``author_run_id`` (``runner.provenance.stamp``). Unanswered: the
    status is not ``answered`` and no live ``type: answer`` row replies to it (a post through
    ``/comms/post`` does not set the status). A blank ``run_id`` matches nothing.
    """
    if not run_id:
        return []
    rows = conn.execute(
        "SELECT q.id FROM comms_messages q "
        "WHERE q.type='question' AND q.author_run_id=? AND q.deleted_at IS NULL "
        "AND lower(trim(COALESCE(q.to_agent, '*'))) IN ('human', '*') "
        "AND COALESCE(q.status, '') != 'answered' "
        "AND NOT EXISTS (SELECT 1 FROM comms_messages a WHERE a.type='answer' "
        "AND a.reply_to=q.id AND a.deleted_at IS NULL) "
        "ORDER BY q.ts ASC, q.id ASC",
        (run_id,),
    ).fetchall()
    return [r["id"] for r in rows]


def waiting_question_ids(fail_reason: str | None) -> list[str]:
    """The question ids a ``waiting_for_answer:<ids>`` reason names; [] for any other reason."""
    if not fail_reason or not fail_reason.startswith(_PREFIX):
        return []
    return [q for q in fail_reason[len(_PREFIX) :].split(",") if q]


def park_task(conn: sqlite3.Connection, task_id: str, question_ids: list[str]) -> bool:
    """Park an ``in_progress`` task on ``question_ids``: ``blocked``, the waiting reason,
    ``waits + 1``, claim released. True when the task was parked."""
    reason = _PREFIX + ",".join(question_ids)
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE comms_messages SET task_status='blocked', claimed_by=NULL, "
            "fail_reason=?, waits=COALESCE(waits, 0)+1 "
            "WHERE id=? AND type='task' AND task_status='in_progress' "
            "AND deleted_at IS NULL",
            (reason, task_id),
        )
        conn.commit()
    return cur.rowcount == 1


def _is_answered(conn: sqlite3.Connection, question_id: str) -> bool:
    row = conn.execute(
        "SELECT q.status, EXISTS (SELECT 1 FROM comms_messages a WHERE a.type='answer' "
        "AND a.reply_to=q.id AND a.deleted_at IS NULL) AS replied "
        "FROM comms_messages q WHERE q.id=?",
        (question_id,),
    ).fetchone()
    if row is None:
        return False
    return row["status"] == "answered" or bool(row["replied"])


def park_and_recheck(
    conn: sqlite3.Connection, task_id: str, question_ids: list[str]
) -> str:
    """``park_task``, then free the task at once when every question is answered now.

    An answer written between the caller's ``open_questions_by_run`` and the park found no
    blocked task to free, so the task would stay parked on an answered question. Returns
    ``parked``, ``released`` (``pending`` again, the ids in ``answered_questions``, the wait
    still counted) or ``not_parked`` (the task was not ``in_progress``).
    """
    if not park_task(conn, task_id, question_ids):
        return "not_parked"
    if question_ids and all(_is_answered(conn, q) for q in question_ids):
        if task_id in release_waiting_tasks(conn, question_ids[0]):
            return "released"
    return "parked"


def task_status(conn: sqlite3.Connection, task_id: str) -> str | None:
    """The task's ``task_status``; None for a missing task."""
    row = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (task_id,)
    ).fetchone()
    return row["task_status"] if row is not None else None


def still_waiting(conn: sqlite3.Connection, task_ids: list[str]) -> list[str]:
    """The ``task_ids`` that still wait: parked on a question, or ``pending`` again after an
    answer and not yet run. A task that ran again (done, failed, in progress) is left out.
    """
    waiting: list[str] = []
    for tid in task_ids:
        row = conn.execute(
            "SELECT task_status, fail_reason FROM comms_messages "
            "WHERE id=? AND deleted_at IS NULL",
            (tid,),
        ).fetchone()
        if row is None:
            continue
        status = row["task_status"]
        if status == "pending" or (
            status == "blocked" and waiting_question_ids(row["fail_reason"])
        ):
            waiting.append(tid)
    return waiting


def _merged_ids(answered_json: str | None, ids: list[str]) -> str:
    try:
        known = json.loads(answered_json) if answered_json else []
    except (TypeError, ValueError):
        known = []
    if not isinstance(known, list):
        known = []
    merged = [str(q) for q in known] + [q for q in ids if q not in known]
    return json.dumps(merged)


def release_waiting_tasks(conn: sqlite3.Connection, question_id: str) -> list[str]:
    """Free every live task parked on ``question_id`` whose questions are now all answered:
    back to ``pending``, the waiting reason cleared, the ids added to ``answered_questions``.
    Returns the freed task ids. A task that still waits on another question stays parked.
    """
    if not question_id:
        return []
    rows = conn.execute(
        "SELECT id, fail_reason, answered_questions FROM comms_messages "
        "WHERE type='task' AND task_status='blocked' AND deleted_at IS NULL "
        "AND fail_reason LIKE 'waiting_for_answer:%' AND instr(fail_reason, ?) > 0",
        (question_id,),
    ).fetchall()
    freed: list[str] = []
    for row in rows:
        ids = waiting_question_ids(row["fail_reason"])
        if question_id not in ids or not all(_is_answered(conn, q) for q in ids):
            continue
        with _get_write_lock(conn):
            cur = conn.execute(
                "UPDATE comms_messages SET task_status='pending', claimed_by=NULL, "
                "fail_reason=NULL, answered_questions=? "
                "WHERE id=? AND task_status='blocked' AND fail_reason=?",
                (
                    _merged_ids(row["answered_questions"], ids),
                    row["id"],
                    row["fail_reason"],
                ),
            )
            conn.commit()
        if cur.rowcount == 1:
            freed.append(row["id"])
    return freed


def release_on_answer(conn: sqlite3.Connection, question_id: str) -> None:
    """``release_waiting_tasks`` for a stored answer, best-effort: the answer is already
    written, so a failure here is logged and never raised to the writer."""
    try:
        freed = release_waiting_tasks(conn, question_id)
        if freed:
            logger.info("answer to %s freed waiting task(s) %s", question_id, freed)
    except Exception:
        logger.warning(
            "releasing tasks waiting on %s failed", question_id, exc_info=True
        )


def task_waits(conn: sqlite3.Connection, task_id: str) -> int:
    """The task's ``waits`` count; 0 for a missing task."""
    row = conn.execute(
        "SELECT waits FROM comms_messages WHERE id=?", (task_id,)
    ).fetchone()
    return int(row["waits"] or 0) if row is not None else 0


def tasks_behind_waiting(conn: sqlite3.Connection, board: str, scope: str) -> set[str]:
    """Ids of the board's tasks whose dependency chain reaches a task parked on a question:
    they wait for an answer, not on an unsatisfiable dependency."""
    rows = conn.execute(
        "SELECT id, depends_on, task_status, fail_reason FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()
    deps: dict[str, list[str]] = {}
    parked: set[str] = set()
    for row in rows:
        try:
            parsed = json.loads(row["depends_on"]) if row["depends_on"] else []
        except (TypeError, ValueError):
            parsed = []
        deps[row["id"]] = [str(d) for d in parsed] if isinstance(parsed, list) else []
        if row["task_status"] == "blocked" and waiting_question_ids(row["fail_reason"]):
            parked.add(row["id"])
    behind: set[str] = set()
    for tid in deps:
        seen: set[str] = set()
        stack = list(deps[tid])
        while stack:
            dep = stack.pop()
            if dep in parked:
                behind.add(tid)
                break
            if dep not in seen:
                seen.add(dep)
                stack.extend(deps.get(dep, []))
    return behind


def question_answers(conn: sqlite3.Connection, question_ids: list[str]) -> list[dict]:
    """``[{question, answer}]`` for each id: the question's text and its latest live answer's
    text (None when it has none). A question that no longer exists is left out."""
    out: list[dict] = []
    for qid in question_ids:
        q = conn.execute(
            "SELECT text FROM comms_messages WHERE id=?", (qid,)
        ).fetchone()
        if q is None:
            continue
        a = conn.execute(
            "SELECT text FROM comms_messages WHERE type='answer' AND reply_to=? "
            "AND deleted_at IS NULL ORDER BY ts DESC LIMIT 1",
            (qid,),
        ).fetchone()
        out.append({"question": q["text"], "answer": a["text"] if a else None})
    return out
