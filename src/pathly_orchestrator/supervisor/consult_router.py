"""Route a run's role question to a consult when it is posted (chief-autopilot-round-two 04).

``on_question`` acts on one posted question, server-driven, with no chief turn. It asks
``consult_routes.route_decision`` (ticket 01):

- ``none`` → nothing (a question to the person or everyone, a tokenless one, one already routed).
- ``person`` → ``hand_to_person`` with the decision's reason.
- ``route`` with no spawn host listening → nothing (``no_host``): the question stays as posted,
  since a change of ``to_agent`` there would rewrite rows other tests read (spec Decisions).
- ``route`` from an asking run whose token names no project root, or whose token's board and
  scope are not the question's → ``hand_to_person``: the consult runs in the asking run's own
  project and board, never in ones the request body names.
- ``route`` → ``record_route`` (insert-or-ignore; False for a duplicate and for a cap a racing
  question reached, so ``route_decision`` is asked again), then ``start`` on a daemon thread named
  ``consult-<question id prefix>``.

A ``start`` that raises hands the question to the person with the error and sets its route
``failed``. ``start_consult`` also answers ``{"started": False, "reason"}`` without raising; then
a route still ``queued`` (nothing else claimed it) is handed on the same way, and a route another
start claimed is left to it.
"""

from __future__ import annotations

import logging
import threading

from .consult_run import start_consult

logger = logging.getLogger(__name__)

BY = "pathly"
THREAD_PREFIX = "consult-"


def on_question(
    question_id: str,
    *,
    project_root: str | None,
    board: str | None,
    scope: str | None,
    broadcast_fn,
    host_present: bool,
    start=None,
) -> str:
    """Route ``question_id``; returns what it did: ``none``, ``person``, ``routed`` or
    ``no_host``. ``project_root``, ``board`` and ``scope`` are the asking run's token's.
    ``start`` defaults to ``consult_run.start_consult`` (read at call time).
    """
    from ..db.connection import get_db
    from ..db.queries import consult_routes

    conn = get_db()
    decision = consult_routes.route_decision(conn, question_id)
    if decision.kind == "route" and not host_present:
        return "no_host"
    if decision.kind == "route":
        refusal = _asker_refusal(conn, question_id, project_root, board, scope)
        if refusal:
            consult_routes.hand_to_person(conn, question_id, refusal, by=BY)
            return "person"
    if decision.kind == "route" and not consult_routes.record_route(
        conn, decision, question_id
    ):
        decision = consult_routes.route_decision(conn, question_id)
        if decision.kind == "route":  # inserted by nobody, yet not routable now
            return "none"
    if decision.kind == "person":
        consult_routes.hand_to_person(conn, question_id, decision.reason, by=BY)
        return "person"
    if decision.kind != "route":
        return "none"
    threading.Thread(
        target=_start,
        args=(question_id, start or start_consult),
        kwargs={
            "project_root": (project_root or "").strip(),
            "broadcast_fn": broadcast_fn,
        },
        name=THREAD_PREFIX + question_id[:8],
        daemon=True,
    ).start()
    return "routed"


def _asker_refusal(
    conn,
    question_id: str,
    project_root: str | None,
    board: str | None,
    scope: str | None,
) -> str | None:
    """Why the asking run's token cannot carry this consult, else None: no project root, or a
    board and scope that are not the question's."""
    if not (project_root or "").strip():
        return "the asking run's token names no project root"
    row = conn.execute(
        "SELECT board, scope FROM comms_messages WHERE id=?", (question_id,)
    ).fetchone()
    asked = (row["board"] or "", row["scope"] or "") if row else ("", "")
    own = (board or "", scope or "")
    if asked != own:
        return (
            f"the question is on board {asked[0]}/{asked[1]}, "
            f"the asking run's is {own[0]}/{own[1]}"
        )
    return None


def _start(question_id: str, start, *, project_root: str, broadcast_fn) -> None:
    """Call ``start`` for a ``queued`` route; a start that raises, or that does not start a route
    left ``queued``, hands the question to the person and fails the route."""
    try:
        result = start(
            question_id,
            project_root=project_root,
            broadcast_fn=broadcast_fn,
            block=False,
        )
    except Exception as exc:
        logger.warning(
            "consult start for question %s raised", question_id, exc_info=True
        )
        _fail(question_id, f"consult start failed: {type(exc).__name__}: {exc}")
        return
    if isinstance(result, dict) and result.get("started"):
        return
    reason = result.get("reason") if isinstance(result, dict) else None
    _fail(
        question_id,
        f"consult did not start: {reason or 'no reason given'}",
        only_queued=True,
    )


def _fail(question_id: str, why: str, *, only_queued: bool = False) -> None:
    """Set the route ``failed`` with ``why``, then hand the question to the person (which keeps
    the ended status). With ``only_queued``, a route no longer ``queued`` is left alone.
    """
    try:
        from ..db.connection import get_db
        from ..db.queries import consult_routes

        conn = get_db()
        if only_queued:
            routes = consult_routes.routes_for_questions(conn, [question_id])
            if not routes or routes[0]["status"] != "queued":
                return
        consult_routes.set_route_status(conn, question_id, "failed", reason=why)
        consult_routes.hand_to_person(conn, question_id, why, by=BY)
    except Exception:
        logger.warning(
            "could not hand question %s to the person", question_id, exc_info=True
        )
