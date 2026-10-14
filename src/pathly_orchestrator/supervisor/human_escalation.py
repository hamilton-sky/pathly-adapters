"""Post an answerable, human-addressed escalation on a run's board.

Without it a headless stop (a human checkpoint, a red base) only parks the run and writes a
file nobody sees. Shared by ``orchestrator_stage`` (the human-checkpoint park) and
``base_smoke`` (the red-base park) so there is one writer.

Best-effort: it never blocks the still-parking run, and it is layer-legal because the
supervisor posts straight through ``db.queries.comms_messages``. The row is server-written
(``system_stamp``), so ``fsm_human_gate`` does not turn it into a second block on the resumed run.
"""

from __future__ import annotations

from .state import logger


def post_human_escalation(state, text: str) -> None:
    """Post *text* as an unacknowledged ``to_agent='human'`` escalation on the run's topic."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_messages import post_message
        from pathly_orchestrator.runner.provenance import system_stamp

        post_message(
            get_db(),
            board="feature",
            scope=state.topic,
            from_agent="system",
            to_agent="human",
            type="escalation",
            text=text,
            goal_id=state.goal_id or None,
            **system_stamp(),
        )
    except Exception as exc:
        logger.warning("human escalation post failed: %s", exc)
