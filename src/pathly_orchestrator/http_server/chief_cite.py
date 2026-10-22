"""The cite rule of the chief gate (chief-agent 10): a chief answers by citing, never by wording.

An answer from a chief token (``/runner/agent-answer``, ``/comms/answer``, and the
acknowledgement of a human-addressed escalation, which is an ``answer`` action) carries ``cite``
and nothing else. ``cite`` is the number of a ``chief_human_messages`` row the hook recorded when
the person submitted a prompt in this chief's tab. The gate checks that the row

* is of kind ``human`` (not the style prompt, not a ``relayed`` message) and of this session;
* was recorded at or after the question was asked: for a run's question
  (``RunnerState._agent_question["asked_at"]``) and for a board row (the ``ts`` of the
  ``question_id`` or of the escalation);
* has not been cited before (``chief_citations`` holds each message once);

and, for a run's topic, that the run belongs to the session's project. A body that also carries
``answer`` or ``option_id`` is refused: the chief cannot word an answer or pick an option for the
person. On success the gate spends the message (``record_citation``) and keeps the message's own
text on ``flask.g`` for the route, which reads its answer through ``answer_text``; so the words an
agent receives are the ones the hook recorded, whatever the chief does with shell quoting. A
caller without a chief token is never touched: ``answer_text`` gives it the ``answer`` it sent.

What this shows is that the words are those of a prompt the hook recorded as one that reached the
chief's tab, relayed to the question the chief picked. Outer whitespace is the one thing a route
may change: ``/runner/agent-answer`` strips the answer before it supplies it, ``/comms/answer``
stores the cited text unstripped (it strips only to see whether it is blank). It does not prove the person meant the words for that question (a chief can
cite an unrelated later remark). A ``human`` row is what the hook endpoint recorded, not proof of
who typed it (the hook's own docstring says why): a headless agent an ``operator`` chief starts
runs as the same OS user and can post a row itself if it reads the session's secret file and
``--session-id``. And the rule guards the chief token's own calls, not a process the chief
starts: that agent can call the unchanged answer routes with no ``cite`` at all.

The acknowledgement of a human escalation is a cited answer too, and it must say who closes the
gate: the body's ``agent`` is stored on the row, so it has to be ``"chief"`` (as ``/comms/post``
needs ``from == "chief"``), else the board would read as if the person closed it.

A citation is spent when the gate lets the call through, whatever the route then does: a topic
with no run (404), a run that is not awaiting an answer (409), a ``text/plain`` body (the gate
reads it with ``force=True``, the route's strict ``get_json()`` answers 415, then 500) and
``/comms/answer`` on a human escalation (the route's 403) all use the message up, and the person
is not told. So a chief, buggy or hostile, can burn any unspent message of its session by naming
a topic with no run or an idle one; the person types again. A target the route rejects for its
shape (a blank or non-string ``topic`` or ``question_id``) spends nothing, and so does one the
gate cannot look up (``chief_bind.is_id``: over 512 characters, a control character or a lone
surrogate), which is left to the route. Both sides of "at or
after" are the wall clock (``time.time()`` for a message and for a run's question, the row's ISO
``ts`` for a board row), so a clock stepped backwards lets an older message pass. A codex chief
records no message, so it can cite nothing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Sequence

from flask import g

from pathly_orchestrator.scope_names import root_spelling

from .chief_bind import is_id
from .chief_project import NOT_OWN, is_own

NOT_CITED = "cite a human message from this chief session"
NOT_CITED_CODEX = (
    f"{NOT_CITED}: a codex chief records none, so it cannot relay an answer"
)
CITE_ONLY = "send cite only: Pathly relays the cited message's text"
ALREADY_CITED = "that message was already cited"
AS_CHIEF = "a chief acknowledges a human escalation as 'chief'"
ACKNOWLEDGE = "/comms/acknowledge"

# The key of each answer route's body that says what the answer is for.
TARGET_KEYS: Mapping[str, str] = {
    "/runner/agent-answer": "topic",
    "/comms/answer": "question_id",
    ACKNOWLEDGE: "message_id",
}


def answer_text(data: Mapping) -> str:
    """The answer a route relays: the text the gate cited for a chief, else the body's own."""
    cited = getattr(g, "chief_cited_text", None)
    return data.get("answer", "") if cited is None else cited


def _not_cited(session: Mapping) -> str:
    return NOT_CITED if session.get("engine") == "claude" else NOT_CITED_CODEX


def _cited_message(conn, session: Mapping, cite: object) -> dict | None:
    """The row ``cite`` names when it is a ``human`` message of this session, else None."""
    from pathly_orchestrator.db.queries.chief import get_human_message

    # Not a bool, a float or a string; and SQLite holds 64 bits, a larger number is no message.
    if type(cite) is not int or abs(cite) >= 2**63:
        return None
    message = get_human_message(conn, cite)
    if (
        message is None
        or message["kind"] != "human"
        or message["run_id"] != session.get("run_id")
    ):
        return None
    return message


def _epoch(stamp: object) -> float | None:
    """A board row's ISO ``ts`` as seconds since the epoch (a naive one is UTC), or None."""
    if not isinstance(stamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _floor(rule: str, session: Mapping, conn, target: str) -> float | str | None:
    """The time a cited message must not precede, a refusal (a string) when the target cannot be
    answered by this chief, or None when there is nothing to compare against. A run that is not
    awaiting an answer, a topic without a run and a row that does not exist are left to the
    route, which answers them (409, 404, 404).
    """
    if rule == "/runner/agent-answer":
        from pathly_orchestrator.supervisor import get_state

        state = get_state(target)
        if state is None:
            return None
        if not is_own(state.project_root, root_spelling(session.get("project_root"))):
            return NOT_OWN
        asked = state._agent_question
        return asked["asked_at"] if isinstance(asked, dict) else None
    row = conn.execute("SELECT ts FROM comms_messages WHERE id=?", (target,)).fetchone()
    if row is None:
        return None
    stamped = _epoch(row["ts"])
    return _not_cited(session) if stamped is None else stamped


def cite_refusal(
    rule: str, session: Mapping, conn, bodies: Sequence[Mapping]
) -> str | None:
    """The reason a chief's answer is refused, or None when it may go on to the route.

    ``bodies`` are the readings of the request body the gate checked (``chief_gate._bodies``);
    the readings must agree on ``cite`` and on the target, and none may carry ``answer`` or
    ``option_id``. On success the message is spent and ``flask.g`` carries what the route reads.
    """
    if any("answer" in body or "option_id" in body for body in bodies):
        return CITE_ONLY
    if rule == ACKNOWLEDGE and any(body.get("agent") != "chief" for body in bodies):
        return AS_CHIEF
    key = TARGET_KEYS[rule]
    asks = [(body.get("cite"), body.get(key)) for body in bodies]
    if any(ask != asks[0] for ask in asks):
        return _not_cited(session)
    cite, target = asks[0]
    message = _cited_message(conn, session, cite)
    if message is None:
        return _not_cited(session)
    if not is_id(target):
        # The route answers for a target it rejects (400) or finds nothing for (404, 409); one
        # the gate cannot look up (a lone surrogate, which SQLite refuses) is the route's too.
        return None
    floor = _floor(rule, session, conn, target)
    if isinstance(floor, str):
        return floor
    if floor is not None and message["ts"] < floor:
        return _not_cited(session)

    from pathly_orchestrator.db.queries.chief import record_citation

    if not record_citation(conn, session["run_id"], message["id"], rule, target):
        return ALREADY_CITED
    if rule == ACKNOWLEDGE:
        g.chief_cited_gate = target
    else:
        g.chief_cited_text = message["text"]
    return None
