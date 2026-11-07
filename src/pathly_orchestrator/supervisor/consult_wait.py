"""A loop drain waits for the consults its parked tasks wait on (chief-autopilot-round-two 06).

A loop task whose attempt asked a role is parked (``task_waits.asked_questions_by_run``). When
the drain ends with such a task and its question's consult is still ``queued`` or ``running``
(``consult_routes.pending_routes``), ``fan_out._drain`` calls ``wait_for_consults``: it polls until
no question those tasks wait on has a pending route, the abort flag is set, or the timeout passes,
and returns the tasks now ``pending`` (an answer's ``release_on_answer`` freed them), which the
drain runs again. A question handed to the person has no pending route, so nothing waits on it.

A consult's delivery ends the route ``answered`` just before it posts the answer row, so a route
``answered`` whose question has no answer yet is waited on too (until the timeout at most).
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional

logger = logging.getLogger("pathly.consult_wait")

# The consult spawn's timeout: the ``timeout=600`` of ``consult_run._default_spawn``'s RunnerState.
CONSULT_SPAWN_TIMEOUT = 600.0
# How long a drain waits for its consults: the spawn's timeout plus 90 seconds. Read at call time
# by ``fan_out._drain``, so a test can lower it.
WAIT_TIMEOUT = CONSULT_SPAWN_TIMEOUT + 90.0
POLL_INTERVAL = 1.0


def _waited_questions(conn, task_ids: list[str]) -> tuple[list[str], list[str]]:
    """(the questions the parked ``task_ids`` wait on, the ids among them still waited for)."""
    from pathly_orchestrator.db.queries.consult_routes import (
        pending_routes,
        routes_for_questions,
    )
    from pathly_orchestrator.db.queries.task_waits import (
        question_answers,
        waiting_question_ids,
    )

    qids: list[str] = []
    for tid in task_ids:
        row = conn.execute(
            "SELECT task_status, fail_reason FROM comms_messages "
            "WHERE id=? AND deleted_at IS NULL",
            (tid,),
        ).fetchone()
        if row is not None and row["task_status"] == "blocked":
            qids.extend(
                q for q in waiting_question_ids(row["fail_reason"]) if q not in qids
            )
    if not qids:
        return [], []
    waited = pending_routes(conn, qids)
    for route in routes_for_questions(conn, qids):
        qid = route["question_id"]
        if route["status"] == "answered" and qid not in waited:
            pairs = question_answers(conn, [qid])
            if pairs and pairs[0]["answer"] is None:
                waited.append(qid)
    return qids, waited


def wait_for_consults(
    task_ids: list[str],
    abort_check: Optional[Callable[[], bool]],
    timeout: float,
) -> list[str]:
    """Wait until no question ``task_ids`` wait on has a ``queued`` or ``running`` route, the
    abort flag is set, or ``timeout`` seconds pass; returns the ``task_ids`` now ``pending``.

    Best-effort: a read that fails is logged and releases nothing (the tasks stay waits).
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.task_waits import task_status

    if not task_ids:
        return []
    conn = get_db()
    deadline = time.monotonic() + max(0.0, float(timeout))
    try:
        while True:
            _, waited = _waited_questions(conn, task_ids)
            if not waited:
                break
            if abort_check is not None and abort_check():
                logger.info("consult wait for %s aborted", task_ids)
                break
            if time.monotonic() >= deadline:
                logger.info(
                    "consult wait for %s timed out after %gs on %s",
                    task_ids,
                    timeout,
                    waited,
                )
                break
            time.sleep(POLL_INTERVAL)
        return [t for t in task_ids if task_status(conn, t) == "pending"]
    except Exception:
        logger.warning("waiting for the consults of %s failed", task_ids, exc_info=True)
        return []
