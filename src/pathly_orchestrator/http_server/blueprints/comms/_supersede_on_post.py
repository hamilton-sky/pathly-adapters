"""Apply a post's optional ``supersedes`` list — the agent-facing supersession write path.

The supersession mechanism was fully built and completely unused: the ``superseded_by``
column exists, ``supersede_message()`` handles not_found/already_superseded, the
``POST /comms/supersede`` route is live, and BOTH ``get_pending_decisions`` and
``get_active_escalations`` already filter on it. Nothing in the agent path ever called it,
so on a representative board ``superseded_by`` was set on 0 of 71 messages and decisions
simply accumulated — an agent reading the injected governance block saw "X remains a hard
human gate" and "X is resolved, unblocked" as equally-live truth.

Closing that needs a write path an agent can reach WITHOUT a second round-trip, which is why
this hangs off ``/comms/post`` rather than asking agents to post-then-supersede: a two-call
protocol fails open (the agent posts, then forgets/errors on call two) and leaves the board
in exactly the state this fixes.

**Deliberately explicit, never inferred.** An earlier sketch had the server auto-supersede the
most semantically-similar prior decision whenever text began "RESOLVED —" / "UNBLOCKED —".
That is rejected: silently retiring governance on an embedding-distance guess turns "nothing
ever closes" into "the wrong thing closed", which is strictly worse — a superseded gate is
invisible to every downstream reader. Supersession is a claim the author makes explicitly.

Best-effort by design: a bad id degrades to a per-id ``skipped`` entry, never a failed post.
The message is already written by the time this runs, and losing a real decision post because
it named a stale id would trade a small problem for a large one.

**A binding directive is retired by the chief alone** (chief-agent 16). The governance block
invites every agent to name an id in ``supersedes``, and ``/comms/supersede`` takes any caller,
so both would retire a standing order. ``is_binding`` and ``chief_may_retire`` are the one test
both paths ask: a row with ``binding = 1`` is left alone unless the caller is a live chief run.
"""

from __future__ import annotations

import logging

from ...run_identity import is_chief_run

# Bounded so a malformed/hostile payload can't turn one post into an unbounded write storm.
MAX_SUPERSEDES = 20


# Governance rows a decision can replace. An escalation is never one of them: a human-addressed
# escalation is a gate only a human acknowledgement closes, and superseding it would retire the
# gate silently (get_active_escalations filters superseded rows out).
SUPERSEDABLE_TYPES = ("decision", "constraint")
_ROW_SQL = (
    "SELECT type, board, scope FROM comms_messages WHERE id=? AND deleted_at IS NULL"
)
# Refusal text of every route that would retire a directive for a caller that may not.
BINDING_REFUSED = "only the chief retires a binding directive"
# The flag ``get_binding_decisions`` reads and ``post_directive`` sets: the one meaning of "binding".
_BINDING_SQL = "SELECT 1 FROM comms_messages WHERE id=? AND binding=1"


def _request_identity():
    """The caller's identity inside a request, else None (a direct call, as in tests)."""
    from flask import has_request_context, request

    if not has_request_context():
        return None
    from pathly_orchestrator.http_server.run_identity import caller_identity

    return caller_identity(request)


def is_binding(conn, message_id: str) -> bool:
    """True when the row is a binding directive (``binding = 1``); a missing row is not one."""
    return conn.execute(_BINDING_SQL, (message_id,)).fetchone() is not None


def chief_may_retire(identity) -> bool:
    """True for a live run whose role is ``chief`` (``run_identity.is_chief_run``) and nobody
    else: not the server secret, not another role's run token, not a request with no token, not
    a call made outside a request (``identity`` None). The chief gate has already checked that
    the session's tier may ``decide`` and that the directive is in the chief's project.
    """
    return is_chief_run(identity)


def _off_token_board(identity, row) -> bool:
    """True when an agent run targets a row off its own token's board and scope."""
    if identity is None or identity.kind != "run":
        return False
    return (row["board"], row["scope"]) != (identity.board, identity.scope)


def refuse_agent_supersede(conn, old_id: str):
    """403 for an agent run superseding through POST /comms/supersede what /comms/post refuses.

    The direct route checks neither type nor board, so an agent could retire a human-addressed
    escalation (silently opening the human gate) or another board's decision. Studio's
    supersede menu sends no run token and keeps working until the UI token (RRP-2b), for every
    row but a binding directive: that one is 403 for any caller that is not a live chief run,
    a request with no token and one with only the server secret included.
    """
    from flask import jsonify

    identity = _request_identity()
    if is_binding(conn, old_id) and not chief_may_retire(identity):
        return jsonify({"error": BINDING_REFUSED}), 403
    if identity is None or identity.kind != "run":
        return None
    row = conn.execute(_ROW_SQL, (old_id,)).fetchone()
    if row is None:
        return None  # the route answers 404
    if row["type"] not in SUPERSEDABLE_TYPES:
        return (
            jsonify({"error": "an agent may supersede only a decision or constraint"}),
            403,
        )
    if _off_token_board(identity, row):
        return jsonify({"error": "an agent may supersede only on its own board"}), 403
    return None


def validate_supersedes(
    value: object, msg_type: object = "decision"
) -> tuple[list[str] | None, str | None]:
    """Return ``(ids, error)``. ``ids`` is None when the field was absent.

    Rejects the malformed shapes at the request boundary (so the caller can 400 before
    writing anything) and de-duplicates while preserving order.
    """
    if value is None:
        return None, None
    if msg_type not in SUPERSEDABLE_TYPES:
        return (
            None,
            "Field 'supersedes' is only accepted on a decision or constraint post",
        )
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None, "Field 'supersedes' must be a list of message-id strings or null"
    ids = [v.strip() for v in value if v.strip()]
    if len(ids) > MAX_SUPERSEDES:
        return None, f"Field 'supersedes' accepts at most {MAX_SUPERSEDES} ids"
    return list(dict.fromkeys(ids)), None  # de-duplicated, order kept


def apply_supersedes(conn, old_ids: list[str], new_id: str) -> dict:
    """Mark each id in *old_ids* superseded by *new_id*.

    Returns ``{"superseded": [...], "skipped": [{"id":…, "reason":…}]}``. ``reason`` is
    ``supersede_message``'s own verdict (``not_found`` / ``already_superseded``), passed
    through unchanged so the agent can tell "you named a stale id" from "someone else got
    there first"; ``self_reference``, ``not_a_decision`` (an escalation, task or note),
    ``other_board`` (not the board and scope the post landed on) and ``binding`` (a directive,
    unless the caller is a live chief run) are refused here.
    """
    result: dict = {"superseded": [], "skipped": []}
    if not old_ids:
        return result
    try:
        from pathly_orchestrator.db.queries.comms import (
            supersede_message as _supersede,
        )
    except (
        Exception
    ):  # pragma: no cover - import failure is not worth failing a post over
        logging.debug("supersede import failed", exc_info=True)
        return result

    new_row = conn.execute(_ROW_SQL, (new_id,)).fetchone()
    identity = _request_identity()
    for old_id in old_ids:
        if old_id == new_id:
            # A message cannot supersede itself: get_pending_decisions filters on
            # `superseded_by IS NULL`, so this would silently retire the post being made.
            result["skipped"].append({"id": old_id, "reason": "self_reference"})
            continue
        old_row = conn.execute(_ROW_SQL, (old_id,)).fetchone()
        if old_row is None:
            result["skipped"].append({"id": old_id, "reason": "not_found"})
            continue
        if old_row["type"] not in SUPERSEDABLE_TYPES:
            result["skipped"].append({"id": old_id, "reason": "not_a_decision"})
            continue
        # Only the board the post lands on: the feature board accepts any role, so a
        # cross-board supersede would let a feature post retire a project or global decision.
        if new_row is None or (old_row["board"], old_row["scope"]) != (
            new_row["board"],
            new_row["scope"],
        ):
            result["skipped"].append({"id": old_id, "reason": "other_board"})
            continue
        # The post's board/scope come from the body; an agent run is bound to its token's.
        if _off_token_board(identity, old_row):
            result["skipped"].append({"id": old_id, "reason": "other_board"})
            continue
        if is_binding(conn, old_id) and not chief_may_retire(identity):
            result["skipped"].append({"id": old_id, "reason": "binding"})
            continue
        try:
            verdict = _supersede(conn, old_id=old_id, new_id=new_id)
        except Exception:
            logging.debug("supersede %s failed", old_id, exc_info=True)
            result["skipped"].append({"id": old_id, "reason": "error"})
            continue
        if verdict == "ok":
            result["superseded"].append(old_id)
        else:
            result["skipped"].append({"id": old_id, "reason": verdict})
    return result


def response_fields(result: dict) -> dict:
    """The keys a /comms/post response adds for its supersedes; none when it sent no ids.

    Each named id lands in exactly one of the two lists, so both empty means none were sent.
    """
    fields: dict = {}
    if result["superseded"] or result["skipped"]:
        fields["superseded"] = result["superseded"]
    if result["skipped"]:
        fields["supersede_skipped"] = result["skipped"]
    return fields
