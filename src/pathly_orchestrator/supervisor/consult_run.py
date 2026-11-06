"""A consult run: one headless agent of a role answers one routed question (round two, 02).

``start_consult`` takes a question whose route (``db/queries/consult_routes``) is ``queued``,
starts a ``consult-<12 hex>`` run of the route's role with the ``planning/consult-answer`` skill,
reads the summary of that run's own ``AGENT_DONE`` and delivers it:

- ``ANSWER: <text>``: an ``answer`` row replying to the question, from the role to the asker,
  stamped with the consult run (``post_message`` frees the tasks parked on the question); a
  ``DECISION: <approach> — <why>`` line from architect, po or designer adds a ``decision`` row
  (binding 0). Route ``answered``.
- ``ANSWER: USER <why>``: the question goes to the person (``hand_to_person``).
- anything else (no ``ANSWER:`` line, no ``AGENT_DONE``, a spawn that raised or timed out): route
  ``failed`` and the question goes to the person.

It does not go through ``board_run.start_board_run``: that takes the board lock the asking goal
run already holds. The spawn is built here the way ``board_run._default_spawn`` builds one.
The consult runs on the asking run's adapter when that adapter has a headless mode, else claude.
"""

from __future__ import annotations

import json
import logging
import re
import secrets
import threading
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("pathly.supervisor")

SKILL = "planning/consult-answer"
DEFAULT_ADAPTER = "claude"
DEFAULT_CLAUDE_MODEL = "claude-sonnet-4-6"
# The roles whose DECISION: line becomes a decision row.
DECISION_ROLES = frozenset({"architect", "po", "designer"})

_USER = re.compile(r"USER(?:\s+(?P<why>.*))?", re.DOTALL)


def parse_summary(summary: str | None) -> tuple[str, str, str | None]:
    """``(kind, text, decision)`` from a consult's summary.

    ``kind`` is ``answer`` (``text`` the answer), ``user`` (``text`` the reason, maybe empty) or
    ``none`` (no ``ANSWER:`` line, or an empty answer). ``decision`` is the text of the first
    ``DECISION:`` line, else None. The answer is the rest of the first ``ANSWER:`` line plus the
    lines after it, without the ``DECISION:`` line.
    """
    lines = str(summary or "").splitlines()
    decision = None
    for line in lines:
        if line.strip().startswith("DECISION:"):
            decision = line.strip()[len("DECISION:") :].strip() or None
            break
    start = next(
        (i for i, line in enumerate(lines) if line.strip().startswith("ANSWER:")), None
    )
    if start is None:
        return "none", "", decision
    first = lines[start].strip()[len("ANSWER:") :].strip()
    user = _USER.fullmatch(first)
    if user:
        return "user", (user.group("why") or "").strip(), decision
    rest = [ln for ln in lines[start + 1 :] if not ln.strip().startswith("DECISION:")]
    text = "\n".join([first, *rest]).strip()
    if not text:
        return "none", "", decision
    return "answer", text, decision


def consult_engine(conn, asking_run_id: str | None, role: str) -> tuple[str, str]:
    """``(adapter, model)`` for a consult: the asking run's adapter when it can run headless,
    else claude; the role's configured model for that adapter, else ``claude-sonnet-4-6`` on
    claude and ``""`` (the engine's own default) on any other adapter."""
    from ..adapters import headless_capable
    from .spawn_policy import effective_model

    adapter = ""
    if asking_run_id:
        row = conn.execute(
            "SELECT adapter FROM run_history WHERE run_id = ?", (asking_run_id,)
        ).fetchone()
        adapter = str(row["adapter"] or "") if row is not None else ""
    if not adapter or not headless_capable(adapter):
        adapter = DEFAULT_ADAPTER
    model = effective_model(role, adapter, "")
    if not model and adapter == DEFAULT_ADAPTER:
        model = DEFAULT_CLAUDE_MODEL
    return adapter, model


def _default_spawn(
    *,
    board: str,
    scope: str,
    prompt: str,
    run_id: str,
    project_root: str,
    model: str,
    adapter: str,
    agent: str,
    broadcast_fn=None,
) -> dict:
    """A headless one-shot of ``agent``, as ``board_run._default_spawn`` builds one (no lock)."""
    from .state import RunnerState
    from .terminal import _run_stage_via_terminal
    from ..runner.telemetry import new_trace_id, scope_tier_for

    state = RunnerState(
        topic=scope,
        flow="consult",
        project_root=project_root,
        model=model,
        timeout=600,
        run_id=run_id,
        current_state=agent,
        current_adapter=adapter,
        interactive=False,
        board_scope=scope,
    )
    state.executor_owned_telemetry = True
    state.scope_tier = scope_tier_for(board)
    state.goal_trace_id = new_trace_id()
    return _run_stage_via_terminal(state, prompt, adapter, model, run_id, broadcast_fn)


def _live_question(conn, question_id: str) -> dict | None:
    row = conn.execute(
        "SELECT * FROM comms_messages WHERE id=? AND type='question' "
        "AND deleted_at IS NULL",
        (question_id,),
    ).fetchone()
    return dict(row) if row is not None else None


def _task_of(conn, route: dict, question: dict) -> dict | None:
    """The asking task: the route's task when it names one, else the asking run's task."""
    from ..db.queries.consult_routes import asking_task

    if route.get("task_id"):
        row = conn.execute(
            "SELECT * FROM comms_messages WHERE id=? AND type='task'",
            (route["task_id"],),
        ).fetchone()
        if row is not None:
            return dict(row)
    return asking_task(conn, question.get("author_run_id"))


def build_prompt(
    question: dict, task: dict | None, role: str, project_root: str, adapter: str
) -> str:
    """The consult's prompt: the skill, the question, the asking task, the feedback folder and
    the board context. Placeholders are filled in the skill body only, never in board text.
    """
    from ..fsm_compose import _inject_prompt_vars
    from ..fsm_ops import _resolve_storage_path
    from ..runner.comms_context import board_context_for
    from ..skills.compose import compose_skill

    board, scope = question["board"], question["scope"]
    storage = Path(str(_resolve_storage_path(None, project_root, scope)))
    body = compose_skill(SKILL, adapter or DEFAULT_ADAPTER, board_default=True)
    body = _inject_prompt_vars(
        body,
        feature=scope,
        project_root=project_root,
        agent_role=role,
        storage_path=storage,
        skill=SKILL,
        board_tier=board if board in ("feature", "project", "global") else "feature",
        run_category="consult",
    )
    parts = [
        body.rstrip("\n"),
        "## The question",
        f"- id: {question['id']}\n- from: {question.get('from_agent') or '?'}",
        str(question.get("text") or ""),
    ]
    if task is not None:
        parts += ["## The asking task", str(task.get("text") or "")]
    parts += [
        "## The feedback folder",
        f"You may write files only under `{storage / 'feedback'}` (and you must not commit).",
    ]
    context = board_context_for(
        board, scope, project_root, str(question.get("text") or ""), role=role
    )
    if context:
        parts.append(context.rstrip("\n"))
    return "\n\n".join(parts) + "\n"


def _agent_done(conn, run_id: str) -> dict | None:
    """The newest ``AGENT_DONE`` payload whose ``run_id`` is the consult run."""
    row = conn.execute(
        "SELECT payload FROM fsm_events WHERE event_type='AGENT_DONE' "
        "AND json_extract(payload, '$.run_id')=? ORDER BY seq DESC LIMIT 1",
        (run_id,),
    ).fetchone()
    if row is None:
        return None
    try:
        payload = json.loads(row["payload"])
    except (TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _measured_ok(
    question_id: str, run_id: str, *, role: str, project_root: str
) -> bool:
    """Whether the consult may be delivered (ticket 03 measures what it changed)."""
    return True


def _fail(conn, question_id: str, role: str, reason: str) -> str:
    from ..db.queries.consult_routes import hand_to_person, set_route_status

    set_route_status(conn, question_id, "failed", reason=reason)
    hand_to_person(
        conn,
        question_id,
        f"the {role} consult did not answer: {reason}",
        by="the server",
    )
    return "failed"


def _deliver(
    conn, question: dict, role: str, run_id: str, kind: str, text: str, decision
) -> str:
    from ..db.queries.comms_messages import post_message
    from ..db.queries.consult_routes import hand_to_person, set_route_status
    from ..runner.provenance import consult_stamp

    qid = question["id"]
    if kind == "user":
        hand_to_person(conn, qid, text or "no reason given", by=role)
        return "to_person"
    board, scope = question["board"], question["scope"]

    def _post(to_agent: str, type_: str, body: str) -> None:
        post_message(
            conn,
            board,
            scope,
            role,
            to_agent,
            type_,
            body,
            reply_to=qid,
            run_id=run_id,
            **consult_stamp(role, run_id),
        )

    if decision and role in DECISION_ROLES:
        _post("*", "decision", decision)
    _post(question.get("from_agent") or "*", "answer", text)
    set_route_status(conn, qid, "answered")
    return "answered"


def _run_consult(
    question: dict,
    route: dict,
    run_id: str,
    *,
    project_root: str,
    broadcast_fn,
    spawn_fn: Callable[..., dict],
) -> str:
    """Spawn the consult, read its summary and deliver it. Returns the route's end status."""
    from ..db.connection import get_db

    conn = get_db()
    qid, role = question["id"], route["role"]
    try:
        adapter, model = consult_engine(conn, question.get("author_run_id"), role)
        task = _task_of(conn, route, question)
        prompt = build_prompt(question, task, role, project_root, adapter)
        spawn_fn(
            board=question["board"],
            scope=question["scope"],
            prompt=prompt,
            run_id=run_id,
            project_root=project_root,
            model=model,
            adapter=adapter,
            agent=role,
            broadcast_fn=broadcast_fn,
        )
    except Exception as exc:
        logger.warning("consult %s for question %s failed: %s", run_id, qid, exc)
        return _fail(conn, qid, role, f"{type(exc).__name__}: {exc}")
    done = _agent_done(conn, run_id)
    if done is None:
        return _fail(conn, qid, role, "no AGENT_DONE")
    kind, text, decision = parse_summary(done.get("summary"))
    if kind == "none":
        return _fail(conn, qid, role, "no ANSWER: line in its summary")
    if not _measured_ok(qid, run_id, role=role, project_root=project_root):
        return "withheld"
    try:
        return _deliver(conn, question, role, run_id, kind, text, decision)
    except Exception as exc:
        logger.warning("consult %s: delivering the answer failed: %s", run_id, exc)
        return _fail(conn, qid, role, f"delivery failed: {type(exc).__name__}")


def start_consult(
    question_id: str,
    *,
    project_root: str,
    broadcast_fn,
    spawn_fn: Optional[Callable[..., dict]] = None,
    block: bool = False,
) -> dict:
    """Start the consult run for ``question_id``, whose route must be ``queued``.

    Returns ``{"started": False, "reason": ...}`` when it cannot start, else ``{"started": True,
    "run_id", "role", "status"}``: ``status`` is the route's end status with ``block=True`` and
    ``running`` otherwise (the consult then runs on a daemon thread).
    """
    from ..db.connection import get_db
    from ..db.queries.consult_routes import (
        CONSULT_RUN_PREFIX,
        routes_for_questions,
        set_route_status,
    )

    conn = get_db()
    question = _live_question(conn, question_id)
    if question is None:
        return {"started": False, "reason": "not a live question"}
    routes = routes_for_questions(conn, [question_id])
    if not routes or routes[0]["status"] != "queued":
        return {"started": False, "reason": "no queued route"}
    route = routes[0]
    run_id = CONSULT_RUN_PREFIX + secrets.token_hex(6)
    set_route_status(conn, question_id, "running", consult_run_id=run_id)
    kwargs = {
        "project_root": project_root,
        "broadcast_fn": broadcast_fn,
        "spawn_fn": spawn_fn or _default_spawn,
    }
    result = {"started": True, "run_id": run_id, "role": route["role"]}
    if block:
        return {**result, "status": _run_consult(question, route, run_id, **kwargs)}
    threading.Thread(
        target=_run_consult,
        args=(question, route, run_id),
        kwargs=kwargs,
        name=run_id,
        daemon=True,
    ).start()
    return {**result, "status": "running"}
