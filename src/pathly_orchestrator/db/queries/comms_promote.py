"""Cross-tier message promotion — copy a decision/constraint UPWARD.

The board has three tiers (feature → project → global) and until this module
knowledge could only ever move DOWN: agents READ all three tiers through context
injection, but the ``<board>`` prompt var an agent writes to is only ever
``feature`` or ``project``, and raw global writes are gated to a tiny role set.
So a decision reached inside a feature run had no path to the boards that outlive
it. The ``promoted_to`` / ``promoted_from`` / ``original_scope`` columns were
reserved in ``migrations.py`` for exactly this and had zero readers; this module
is their first one.

Promotion COPIES, it never moves. The source row stays on the board where the
decision was actually reached, because that board is the audit record of HOW it
was reached — moving it would delete the reasoning trail to publish the
conclusion. The copy carries a back-pointer so the two are always joinable.

Layer rule: ``db/`` imports nothing internal (no runner/supervisor/http_server).
Embedding the new row — without which a promoted message is invisible to the
semantic retrieval that is the entire point of promoting it — is therefore the
caller's job, in the blueprint layer, using the same ``_EMBED_TYPES`` /
``embed_async`` pair as ``POST /comms/post``.
"""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock
from .comms_messages import post_message

# Tier ordering. Promotion is only ever STRICTLY upward: a "promotion" that moved
# a global constraint down onto one feature board would silently fork the shared
# rule into a per-feature copy that later edits to the global row never reach.
_TIER_RANK: dict[str, int] = {"feature": 0, "project": 1, "global": 2}

# Only conclusions promote. A `discovery` is a run's raw observation and a
# `status`/`nudge` is run chatter — promoting those is how a global board fills
# with noise until the semantic retrieval that reads it stops being useful, which
# costs every later run on every board. `decision` and `constraint` are the two
# types that are already the distilled OUTPUT of a run, so they are the two that
# are worth carrying across tier boundaries.
PROMOTABLE_TYPES: frozenset[str] = frozenset({"decision", "constraint"})


def is_upward(from_board: str, to_board: str) -> bool:
    """True when *to_board* is a strictly higher tier than *from_board*."""
    src = _TIER_RANK.get((from_board or "").strip())
    dst = _TIER_RANK.get((to_board or "").strip())
    if src is None or dst is None:
        return False
    return dst > src


def find_existing_promotion(
    conn: sqlite3.Connection,
    source_id: str,
    to_board: str,
    to_scope: str,
) -> dict | None:
    """Return the live copy of *source_id* already sitting on (to_board, to_scope).

    Keyed off the COPY's ``promoted_from`` rather than the source's
    ``promoted_to``: one message may legitimately be promoted to more than one
    tier (feature→project AND feature→global), and the source has only ONE
    forward pointer — so checking the forward pointer alone would report "not
    promoted yet" for whichever tier it is not currently pointing at, and insert
    a duplicate on every retry.
    """
    row = conn.execute(
        "SELECT id, board, scope, type, text, from_agent FROM comms_messages "
        "WHERE promoted_from=? AND board=? AND scope=? AND deleted_at IS NULL "
        "ORDER BY ts DESC LIMIT 1",
        (source_id, to_board, to_scope),
    ).fetchone()
    return dict(row) if row is not None else None


def promote_message(
    conn: sqlite3.Connection,
    message_id: str,
    to_board: str,
    to_scope: str,
    promoted_by: str,
) -> dict:
    """Copy a decision/constraint onto a higher board tier, with provenance.

    Returns a status dict the HTTP layer maps onto a response:

    ``{"status": "not_found"}``
        No live (non-deleted) message with that id.
    ``{"status": "not_promotable", "type": <type>}``
        Source is not a ``decision``/``constraint`` — see PROMOTABLE_TYPES.
    ``{"status": "not_upward", "from_board": …, "to_board": …}``
        Sideways or downward — see ``is_upward``.
    ``{"status": "ok", "already_promoted": bool, "message_id": …, …}``
        The row on the target board. ``already_promoted`` is True when this exact
        promotion already existed; the caller uses it to skip re-embedding a row
        whose vector is already stored, and to skip re-broadcasting.

    ``promoted_by`` becomes the copy's ``from_agent`` — the role accountable for
    putting it on the higher board, which is also the role the caller's
    permission gate checked. The ORIGINAL author is never lost: it is one join
    away through ``promoted_from``.
    """
    src = conn.execute(
        "SELECT id, board, scope, from_agent, type, text, original_scope "
        "FROM comms_messages WHERE id=? AND deleted_at IS NULL",
        (message_id,),
    ).fetchone()
    if src is None:
        return {"status": "not_found"}

    src_type = (src["type"] or "").strip()
    if src_type not in PROMOTABLE_TYPES:
        return {"status": "not_promotable", "type": src_type}

    from_board = (src["board"] or "").strip()
    if not is_upward(from_board, to_board):
        return {
            "status": "not_upward",
            "from_board": from_board,
            "to_board": (to_board or "").strip(),
        }

    existing = find_existing_promotion(conn, message_id, to_board, to_scope)
    if existing is not None:
        return {
            "status": "ok",
            "already_promoted": True,
            "message_id": existing["id"],
            "source_id": message_id,
            "board": existing["board"],
            "scope": existing["scope"],
            "type": existing["type"],
            "text": existing["text"],
        }

    # Carry the TRUE origin through a chain (feature→project→global): a chained
    # promotion whose original_scope pointed at the intermediate project board
    # would claim the constraint was authored there, erasing the feature it
    # actually came from. First promotion: src["original_scope"] is NULL, so this
    # is exactly the source's own scope, as the contract specifies.
    origin_scope = (src["original_scope"] or "").strip() or (src["scope"] or "")

    # Reuse post_message rather than hand-rolling the INSERT: it owns id/ts
    # generation and is the row shape every reader (and the comms_fts triggers)
    # already expects. Text is copied VERBATIM so the promoted row embeds to the
    # same point in vector space as the decision it carries — an attribution
    # preamble would drift the copy away from the query that should find it.
    new_id = post_message(
        conn,
        board=to_board,
        scope=to_scope,
        from_agent=promoted_by,
        type=src_type,
        text=src["text"] or "",
    )

    with _get_write_lock(conn):
        conn.execute(
            "UPDATE comms_messages SET promoted_from=?, original_scope=? WHERE id=?",
            (message_id, origin_scope, new_id),
        )
        # Forward pointer = the LATEST promotion. It is a convenience only; the
        # authoritative, complete provenance graph is the promoted_from column on
        # each copy (a single TEXT column cannot hold two targets).
        conn.execute(
            "UPDATE comms_messages SET promoted_to=? WHERE id=?",
            (new_id, message_id),
        )
        conn.commit()

    return {
        "status": "ok",
        "already_promoted": False,
        "message_id": new_id,
        "source_id": message_id,
        "board": to_board,
        "scope": to_scope,
        "type": src_type,
        "text": src["text"] or "",
    }
