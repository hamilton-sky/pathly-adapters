"""Feedback rounds: how many times ``complete_stage`` has routed each feedback file.

``engine_transitions.route_feedback`` picks a file's role from this count through the flow's
``escalation_routing`` (rounds 1-2 the owner, round 3 the specialist, round 4 a human), and
the retry-ladder prompt reads the same number. Nothing used to write it, so in a headless
run every round was round 1 and the ladder never climbed.

The count lives in ``fsm_state`` (the DB) as ``retry_count_by_key: {"FILE.md": n}``, written
here, read here, never from ``STATE.json`` (state-one-authority). Its lifetime:

* ``record_round`` adds one each time ``complete_stage`` routes the file to an agent;
* a round routed to ``human`` clears that file's count, so the ladder starts again at
  round 1 once the human has had it (a resumed run whose gate still fails goes back to the
  owner rather than straight back to the human);
* ``complete_stage`` drops every count when it commits a transition: the stage the file
  blocked was passed, so a later failure is a new problem.

Keys written by older runs as ``conv-N:FILE.md`` are read as ``FILE.md`` (the highest wins).
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("pathly.fsm")

KEY = "retry_count_by_key"


def _normalized(raw) -> dict[str, int]:
    out: dict[str, int] = {}
    if not isinstance(raw, dict):
        return out
    for key, count in raw.items():
        fname = key.split(":", 1)[1] if ":" in key else key
        try:
            out[fname] = max(out.get(fname, 0), int(count or 0))
        except (TypeError, ValueError):
            continue
    return out


def read_retry_counts(storage_path: Path) -> dict[str, int]:
    """``{FILE.md: rounds already routed}`` from ``fsm_state``. ``{}`` when unreadable."""
    try:
        from pathly_orchestrator import eventlog

        state = eventlog.read_state(str(storage_path)) or {}
    except Exception:
        return {}
    return _normalized(state.get(KEY))


def record_round(storage_path: Path, feedback: dict, flow: dict | None) -> None:
    """Count one routed round of ``feedback["file"]``; a round for ``human`` clears it.

    Best-effort: a failed write is logged and the round goes uncounted (the ladder then
    climbs one round later), never an error in ``complete_stage``.
    """
    filename = feedback.get("file")
    if not filename:
        return
    try:
        from pathly_orchestrator import eventlog

        state = eventlog.read_state(str(storage_path))
        if state is None:
            return
        counts = _normalized(state.get(KEY))
        if feedback.get("target_agent") == "human":
            if filename not in counts:
                return
            del counts[filename]
        else:
            counts[filename] = counts.get(filename, 0) + 1
        updated = {k: v for k, v in state.items() if k != "updated_at"}
        updated[KEY] = counts
        eventlog.write_state(str(storage_path), updated, flow)
    except Exception as exc:
        logger.warning(
            "feedback_rounds: could not record a round of %s: %s", filename, exc
        )
