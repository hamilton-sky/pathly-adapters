"""Tasks that wait on a question: park a task on its run's open questions, free it on an answer.

A board or single run that posted a ``question`` to ``human`` (or ``*``) and ended with its task
still ``in_progress`` parks the task instead of failing it (chief-autopilot 06, spike S5):
``task_status='blocked'``, ``fail_reason='waiting_for_answer:<id>[,<id>]'`` and ``waits + 1``.
``attempts`` is left alone (the loop scheduler builds run ids from it, so it only grows); every
attempt limit compares ``attempts - waits``. An answer (``answer_question`` or a ``type: answer``
post with ``reply_to``) frees every task whose questions are then all answered: back to
``pending``, the reason cleared, the question ids kept in ``answered_questions`` (a JSON list)
for the next attempt. Questions to a role (``to: architect``) park a loop task too
(``asked_questions_by_run``, chief-autopilot-round-two 06); a single run reads only
``open_questions_by_run``. An answer written by the asking run itself does not count: such a
question is neither listed nor answered. A loop park past ``wait_ceiling`` waits is held for the
person instead of being released at once (``park_and_recheck(hold_over=...)``).

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
# Waits a loop task may have past ``consult.max_per_task`` before a park is held for the person.
WAIT_MARGIN = 2


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


def asked_questions_by_run(conn: sqlite3.Connection, run_id: str) -> list[str]:
    """Ids of every question the run asked that its attempt did not see answered, oldest first.

    ``open_questions_by_run`` (open questions to ``human`` or ``*``) plus each live question the
    run posted to a role in ``consult_routes.CONSULT_ROLES`` or that has a route row (one handed
    on to the person is addressed to ``human`` now), answered or not: an answer that came while
    the attempt ran was never read by it. A question whose only answers were written by the
    asking run itself (``author_run_id``) is left out: the run read its own answer, and counting
    it would give the task a free attempt each time. Each id once. A blank ``run_id`` matches
    nothing.
    """
    if not run_id:
        return []
    # Imported here: consult_routes imports comms_messages, which imports this module.
    from .consult_routes import CONSULT_ROLES

    rows = conn.execute(
        "SELECT q.id FROM comms_messages q "
        "WHERE q.type='question' AND q.author_run_id=? AND q.deleted_at IS NULL "
        "AND (q.id IN (SELECT value FROM json_each(?)) "
        "OR lower(trim(COALESCE(q.to_agent, ''))) IN (SELECT value FROM json_each(?)) "
        "OR EXISTS (SELECT 1 FROM consult_routes r WHERE r.question_id=q.id)) "
        "AND NOT (EXISTS (SELECT 1 FROM comms_messages a WHERE a.type='answer' "
        "AND a.reply_to=q.id AND a.deleted_at IS NULL AND a.author_run_id=q.author_run_id) "
        "AND NOT EXISTS (SELECT 1 FROM comms_messages a WHERE a.type='answer' "
        "AND a.reply_to=q.id AND a.deleted_at IS NULL "
        "AND COALESCE(a.author_run_id, '') != q.author_run_id)) "
        "ORDER BY q.ts ASC, q.id ASC",
        (
            run_id,
            json.dumps(open_questions_by_run(conn, run_id)),
            json.dumps(list(CONSULT_ROLES)),
        ),
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
    """Answered by someone other than the asking run: a live answer row from another (or no)
    run, or the ``answered`` status with no answer row from the asking run."""
    row = conn.execute(
        "SELECT q.status, EXISTS (SELECT 1 FROM comms_messages a WHERE a.type='answer' "
        "AND a.reply_to=q.id AND a.deleted_at IS NULL AND (q.author_run_id IS NULL "
        "OR COALESCE(a.author_run_id, '') != q.author_run_id)) AS replied, "
        "EXISTS (SELECT 1 FROM comms_messages a WHERE a.type='answer' AND a.reply_to=q.id "
        "AND a.deleted_at IS NULL AND a.author_run_id=q.author_run_id) AS self_replied "
        "FROM comms_messages q WHERE q.id=?",
        (question_id,),
    ).fetchone()
    if row is None:
        return False
    if row["replied"]:
        return True
    return row["status"] == "answered" and not row["self_replied"]


def wait_ceiling(conn: sqlite3.Connection) -> int:
    """The waits a loop task may reach before a park is held for the person:
    ``consult.max_per_task`` plus ``WAIT_MARGIN``."""
    # Imported here: consult_routes imports comms_messages, which imports this module.
    from .consult_routes import consult_limits

    return consult_limits(conn)[0] + WAIT_MARGIN


def park_and_recheck(
    conn: sqlite3.Connection,
    task_id: str,
    question_ids: list[str],
    hold_over: int | None = None,
) -> str:
    """``park_task``, then free the task at once when every question is answered now.

    An answer written between the caller's ``open_questions_by_run`` and the park found no
    blocked task to free, so the task would stay parked on an answered question. Returns
    ``parked``, ``released`` (``pending`` again, the ids in ``answered_questions``, the wait
    still counted) or ``not_parked`` (the task was not ``in_progress``). Once the park is
    committed it never raises: a recheck that fails is logged and the task stays ``parked``
    (an answer's own ``release_on_answer`` still frees it). A task an answer freed between the
    park and the recheck reads ``released``. With ``hold_over``, a task whose ``waits`` is now
    above it is not freed at once: ``held`` (parked for the person; a later answer to one of
    its questions frees it as usual).
    """
    if not park_task(conn, task_id, question_ids):
        return "not_parked"
    try:
        if hold_over is not None and task_waits(conn, task_id) > hold_over:
            logger.warning(
                "task %s has waited %d times (limit %d): held for the person",
                task_id,
                task_waits(conn, task_id),
                hold_over,
            )
            return "held"
        if question_ids and all(_is_answered(conn, q) for q in question_ids):
            release_waiting_tasks(conn, question_ids[0])
        if task_status(conn, task_id) == "pending":
            return "released"
    except Exception:
        logger.warning("recheck of parked task %s failed", task_id, exc_info=True)
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


def restore_freed_waits(
    conn: sqlite3.Connection,
    board: str,
    scope: str,
    waited: list[str],
    deadlocked: list[str],
) -> list[str]:
    """Undo the deadlock mark on the tasks an answer freed during a drain's deadlock check.

    A task that waited in the drain and was freed after the scheduler's last ready read is
    ``pending`` and no longer behind a wait, so ``task_retry.detect_deadlocks`` marks it, and the
    tasks that depend on it, deadlocked. Each of ``deadlocked`` that is in ``waited``, or whose
    dependency chain reaches one, goes back to ``pending``. Returns the ids restored.
    """
    freed = set(deadlocked) & set(waited)
    if not freed:
        return []
    rows = conn.execute(
        "SELECT id, depends_on FROM comms_messages "
        "WHERE board=? AND scope=? AND type='task' AND deleted_at IS NULL",
        (board, scope),
    ).fetchall()
    deps: dict[str, list[str]] = {}
    for row in rows:
        try:
            parsed = json.loads(row["depends_on"]) if row["depends_on"] else []
        except (TypeError, ValueError):
            parsed = []
        deps[row["id"]] = [str(d) for d in parsed] if isinstance(parsed, list) else []
    restored: list[str] = []
    for tid in deadlocked:
        seen: set[str] = set()
        stack = [tid]
        while stack and not freed.intersection(stack):
            dep = stack.pop()
            if dep not in seen:
                seen.add(dep)
                stack.extend(deps.get(dep, []))
        if not stack:
            continue
        with _get_write_lock(conn):
            cur = conn.execute(
                "UPDATE comms_messages SET task_status='pending', fail_reason=NULL "
                "WHERE id=? AND task_status='blocked' AND fail_reason LIKE 'deadlocked:%'",
                (tid,),
            )
            conn.commit()
        if cur.rowcount == 1:
            restored.append(tid)
    return restored


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
