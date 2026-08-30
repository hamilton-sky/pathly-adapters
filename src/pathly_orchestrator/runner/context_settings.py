"""Tunables for the board-context Context channel — how much board an agent sees.

Two numbers decide the size of every ``## Communication Board`` block Pathly injects
into a prompt: the per-tier RESULT COUNT (``k``) the semantic search may keep, and the
CHARACTER BUDGET those kept lines are rendered against. They are a **pair**, and
changing one alone is half a change: ``k`` binds first in the intended case (5+3+2 = 10
messages, and ``fragments/comms-post.md`` tells agents to keep a post to 1–2 sentences
≈ 150–250 chars → ~2000 chars rendered), while the budget is the backstop for when an
agent writes a wall of text anyway.

Why this module exists: the previous values were bare literals — ``CONTEXT_CHAR_BUDGET
= 2000`` in ``context_budget.py`` and ``3``/``2``/``1`` inline in
``comms_context.enabled_boards`` — with **no recorded justification**. ``git log -S``
traces the 2000 to an unrelated session-handoff commit, and the spec
(``pathly/features/comms-board/MEMORY-CONSOLIDATION.md``) mentions it only in passing.
Four lines above the k-ladder sit the per-tier cosine cutoffs, which carry a written
calibration against a live board with measured distance ranges: those were *measured*,
these two were *picked*. So both now get (a) a deliberately chosen default with the
reasoning written down here, (b) an app_settings override so a board can be retuned
without a release, and (c) a measurement path — every prompt build records a
``BOARD_CONTEXT`` event (see ``context_record.py``) carrying the volume actually
rendered vs dropped and the budget+k that were in force, so the NEXT move on these
numbers is made from data rather than taste.

**Reading/writing the live values needs no new route** — the generic settings API in
``http_server/blueprints/ops/db_api_admin.py`` already reads and writes arbitrary keys::

    GET  /db/settings                                    → every key, these included
    PUT  /db/settings/board_context.char_budget   {"value": "6000"}
    PUT  /db/settings/board_context.k_feature     {"value": "8"}

Values are read at CALL time (same contract as ``code_context.backend``), so an edit
takes effect on the next prompt with no server restart.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Defaults, chosen deliberately (see module docstring for what they replace).
#
# char_budget 4000 (was 2000): the k-ladder below admits at most 10 messages and a
# board post is ~150–250 chars, so the intended steady state renders ~2000 chars and the
# budget never binds. 2000 sat exactly ON that steady state — it started truncating the
# moment ONE agent wrote a long note, dropping the cross-tier (project/global) lines that
# are the expensive ones to re-derive. 4000 leaves the cap where it belongs: a guard
# against a pathological board, not a routine editor.
DEFAULT_CHAR_BUDGET = 4000
# k 5/3/2 (was 3/2/1): 3 feature slots is one governance-adjacent note plus two others —
# thin enough that a board with any activity evicts the older context every stage. The
# ladder shape (own board widest, global narrowest) is kept because it mirrors the
# per-tier distance gates: attention narrows as the board gets further from the task.
DEFAULT_K = {"feature": 5, "project": 3, "global": 2}

# app_settings keys, dotted style to match ``code_context.backend``.
SETTING_KEYS = {
    "char_budget": "board_context.char_budget",
    "k_feature": "board_context.k_feature",
    "k_project": "board_context.k_project",
    "k_global": "board_context.k_global",
}

# Bounds are not validation theatre — they are the range in which the number still MEANS
# something. Outside it the value is a typo (a stray minus, an extra zero) and must never
# reach the renderer.
#   char_budget floor 200: one rendered line is a ~150–250 char post plus its
#     "[from → to, stage, age, confidence]" header, and select_within_budget always keeps
#     at least one entry — so below ~200 the cap stops changing anything while still
#     claiming to be a cap.
#   char_budget ceiling 40000 (~10k tokens): past this the Context channel outweighs the
#     skill body + pipeline history + code block it exists to SUPPORT, burying the actual
#     task it was injected to inform.
CHAR_BUDGET_BOUNDS = (200, 40_000)
#   k floor 0 is legal and useful: it mutes one tier's semantic pull without touching the
#     board_scope Reads toggle (governance still injects unconditionally, by design).
#   k ceiling 25: each tier over-fetches k + governance + 4 rows and formats every keeper,
#     and the char budget drops nearly all of them long before 25 — a larger k buys
#     latency, not context.
K_BOUNDS = (0, 25)


def _get_int(key: str, default: int, bounds: tuple[int, int]) -> int:
    """Read an int setting from app_settings, or *default*.

    Never raises — a missing row, an unreachable/locked DB, a non-numeric value and an
    out-of-range value all yield *default*, because a config lookup must never break
    prompt assembly. This is the exact contract of ``runner/code_context.py::_get_setting``
    (which this mirrors), for an int instead of a string. ``runner -> db`` is an allowed
    downward import.

    Out-of-range falls back rather than CLAMPS on purpose: a clamped value silently
    renders a board nobody configured, while the default is the one number that is
    documented here and in the tests.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), key, None)
    except Exception:
        logger.debug("context_settings: setting %r lookup failed", key, exc_info=True)
        return default
    try:
        val = int(str(raw).strip())
    except (TypeError, ValueError):
        logger.debug("context_settings: setting %r is not an int (%r)", key, raw)
        return default
    lo, hi = bounds
    if val < lo or val > hi:
        logger.debug("context_settings: setting %r out of range (%r)", key, val)
        return default
    return val


def resolve_context_limits() -> dict[str, int]:
    """Return ``{char_budget, k_feature, k_project, k_global}`` for THIS call.

    Resolved per call, not at import, so a ``PUT /db/settings/board_context.*`` takes
    effect on the next prompt build without restarting the FSM server. The returned dict
    doubles as the "settings in force" half of the ``BOARD_CONTEXT`` telemetry record —
    the keys are already the event's field names, so a later reader can correlate what
    was rendered against the config that produced it.
    """
    return {
        "char_budget": _get_int(
            SETTING_KEYS["char_budget"], DEFAULT_CHAR_BUDGET, CHAR_BUDGET_BOUNDS
        ),
        "k_feature": _get_int(
            SETTING_KEYS["k_feature"], DEFAULT_K["feature"], K_BOUNDS
        ),
        "k_project": _get_int(
            SETTING_KEYS["k_project"], DEFAULT_K["project"], K_BOUNDS
        ),
        "k_global": _get_int(SETTING_KEYS["k_global"], DEFAULT_K["global"], K_BOUNDS),
    }
