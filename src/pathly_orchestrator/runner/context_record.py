"""Measurement for the board-context Context channel — what was rendered vs dropped.

``retrieve_board_context`` already counted the four channels (governance / referenced /
semantic / catalog), but that dict had exactly one consumer — the read-only
``POST /comms/agent-context/preview`` endpoint — and was never persisted. So the budget
and k-ladder in ``context_settings.py`` had no data behind them and the next tuning pass
would have been another guess.

This module closes that loop: it summarises the volume the Context channel actually
rendered per tier and how much the budget dropped, and persists one ``BOARD_CONTEXT``
event per prompt build alongside the budget+k that were in force for that call.

Sink choice: ``eventlog.append_event`` writes to ``fsm_events``, which is keyed by the
run identity we already have (storage dir → project_root + feature slug) and is already
exported to ``EVENTS.jsonl``. ``db/queries/fsm_events.append_event`` only fires the
invocation projection for ``AGENT_DONE``/``BILLING_UPDATE``, so a new ``BOARD_CONTEXT``
type is inert to telemetry/billing — it adds a row and nothing else. It is likewise
absent from ``eventlog._TOAST_EVENTS`` (no Studio toast) and is not a
``STATE_TRANSITION`` (no state validation).

Wired from ``fsm_compose.build_prompt`` — every stage of every FSM/team/consultation run.
The other two prompt-build paths, ``supervisor/board_run.py`` (490) and
``supervisor/scheduler.py`` (433), are frozen at their ``scripts/file_size_baseline.txt``
size and may only SHRINK, so they cannot take the extra argument today; both already
accept ``storage_path`` through ``board_context_for``, so each is a one-line opt-in once
those files are split.

Reading the data back::

    sqlite3 ~/.pathly/pathly.db \\
      "SELECT ts, feature, payload FROM fsm_events WHERE event_type='BOARD_CONTEXT'"

or, per feature, ``python -m pathly_orchestrator.eventlog events pathly/features/<name>``
(the same events land in that feature's ``EVENTS.jsonl`` export).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Unit note: the fields below are named ``*_chars``, not ``*_bytes``, because the budget
# charges CHARACTERS (``len(line)`` in select_within_budget). Counting bytes would
# silently disagree with the cap on any non-ASCII board post, and the whole point of this
# record is to be comparable to the budget that produced it.

# The tiers the rendered/omitted volume is broken down by — the same ladder the budget
# splits along (context_budget.CONTEXT_BUDGET_WEIGHTS), so a record can be read straight
# against the per-tier share it was charged to.
_TIERS = ("feature", "project", "global")


def render_stats(entries: list[tuple[str, str]], kept_idx: list[int]) -> dict[str, int]:
    """Summarise one Context-channel render: what survived the budget, what didn't.

    *entries* is the ``(tier, rendered_line)`` list handed to ``select_within_budget``
    and *kept_idx* its return value, so this measures the REAL rendered output rather
    than re-deriving it. Returns flat ``int`` values only — the caller merges them into
    the ``counts`` dict (typed ``dict[str, int]``) and into the event payload.
    """
    kept = set(kept_idx)
    stats = {f"rendered_chars_{t}": 0 for t in _TIERS}
    stats["rendered_entries"] = len(kept)
    stats["rendered_chars"] = 0
    stats["omitted_entries"] = 0
    stats["omitted_chars"] = 0
    for idx, (tier, line) in enumerate(entries):
        size = len(line)
        if idx in kept:
            stats["rendered_chars"] += size
            key = f"rendered_chars_{tier}"
            if key in stats:  # an unknown tier still counts toward the total
                stats[key] += size
        else:
            stats["omitted_entries"] += 1
            stats["omitted_chars"] += size
    return stats


def record_board_context(storage_path: str | None, stats: dict[str, int]) -> None:
    """Append one ``BOARD_CONTEXT`` event for this prompt build. Best-effort.

    *storage_path* is the run's storage dir — the run identity ``eventlog`` keys events
    by. ``None``/empty means the caller is not a prompt build (notably the read-only
    ``/comms/agent-context/preview`` endpoint, whose contract is "no DB writes"), so
    nothing is written.

    Wrapped and never raising, exactly like the invocation-projection hook it sits beside
    in ``db/queries/fsm_events.append_event``: a telemetry write must never break prompt
    assembly. ``create_dir=False`` because we only have a run's storage path and mkdir-ing
    a resolved ``features/<name>`` default would plant an empty decoy dir that then wins
    ``_resolve_storage_path``'s existence probe (see ``eventlog.append_event``).
    """
    if not storage_path:
        return
    try:
        from pathly_orchestrator import eventlog

        event: dict = {"type": "BOARD_CONTEXT"}
        event.update({k: int(v) for k, v in stats.items()})
        eventlog.append_event(str(storage_path), event, create_dir=False)
    except Exception:
        logger.debug("context_record: BOARD_CONTEXT write failed", exc_info=True)
