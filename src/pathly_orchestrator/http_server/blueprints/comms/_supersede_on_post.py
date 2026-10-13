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
"""

from __future__ import annotations

import logging

# Bounded so a malformed/hostile payload can't turn one post into an unbounded write storm.
MAX_SUPERSEDES = 20


def validate_supersedes(value: object) -> tuple[list[str] | None, str | None]:
    """Return ``(ids, error)``. ``ids`` is None when the field was absent.

    Rejects the malformed shapes at the request boundary (so the caller can 400 before
    writing anything) and de-duplicates while preserving order.
    """
    if value is None:
        return None, None
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
    there first" — and ``self_reference`` for the one case the query layer cannot see.
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

    for old_id in old_ids:
        if old_id == new_id:
            # A message cannot supersede itself: get_pending_decisions filters on
            # `superseded_by IS NULL`, so this would silently retire the post being made.
            result["skipped"].append({"id": old_id, "reason": "self_reference"})
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
