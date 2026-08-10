"""unified-ai-routing Conv 6 — mirror FSM phase boundaries onto the feature board.

`record_phase` appends PHASE_START/PHASE_DONE to the event log; this ALSO posts a
`phase`-type comms message so the Command Center shows live pipeline progress in
BOTH interactive (team-http) and headless (supervisor) runs. Best-effort: it never
raises and never blocks phase logging.

`phase` messages are deliberately EXCLUDED from `retrieve_board_context`
(`runner/comms_context.py` `_is_context`), so they never enlarge the board block
injected into headless CLI-engine prompts — observability without prompt cost.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def post_phase_to_board(
    feature: str,
    agent: str,
    phase: str,
    event_type: str,
    conv: int | None = None,
) -> None:
    """Post a phase-boundary marker to the feature board. Never raises."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import post_message
        from pathly_orchestrator.db.queries.run_history import (
            latest_running_run_id_for_feature,
        )
        from pathly_orchestrator.http_server.sse import _broadcast_comms

        conn = get_db()
        # Correlate to the live run so this phase marker streams to that run's RunDetail Board/Phases
        # via the T3 per-run feed (record_phase carries no run_id). None → the time-window fallback.
        run_id = latest_running_run_id_for_feature(conn, feature)
        verb = "started" if event_type == "PHASE_START" else "done"
        message_id = post_message(
            conn,
            board="feature",
            scope=feature,
            from_agent=agent or "system",
            to_agent="*",
            type="phase",
            text=f"{phase} {verb}",
            stage=phase,
            conv=conv,
            run_id=run_id,
        )
        _broadcast_comms(
            feature,
            {
                "type": "COMMS_UPDATE",
                "event": "phase",
                "scope": feature,
                "msg_type": "phase",
                "message_id": message_id,
                # run_id → sse._broadcast_comms tees this onto /events/runs?run_id=… (live push).
                "run_id": run_id,
            },
        )
    except Exception:
        logger.debug("post_phase_to_board failed", exc_info=True)
