"""Telling a human why a compiled-flow run stopped.

Split out of ``compiled_flow.py`` (SOLID rule #2 — extend by adding files): that module owns
walking a flow's states, this one owns the one thing it has to say to a person when it can't
go further. A compiled run cannot park and resume, so reaching a human is always terminal —
which makes the wording the ONLY record of what happened, and worth getting right.

Two very different situations both surface as ``target_agent == "human"``:

- ``attempts == 0`` — the flow's own ``feedback_routing`` sends this file straight to a
  person (``HUMAN_QUESTIONS.md``, ``BLOCKED_ON_HUMAN.md``, ``REPRO_QUESTIONS.md``). Someone
  is being ASKED something.
- ``attempts > 0`` — ``escalation_routing`` climbed its tiers and ran out after that many
  failed rounds. Nobody is being asked anything; N agents tried and could not fix it.

Collapsing those into one "human checkpoint required" line loses the distinction that tells
the reader whether to answer a question or to go look at the code.
"""

from __future__ import annotations

from typing import Optional

from .state import logger


def escalation_reason(attempts: int, file_name: str) -> str:
    """Half-sentence naming which of the two paths above brought the run here."""
    if attempts <= 0:
        return f"the flow routes {file_name} to a human"
    rounds = "round" if attempts == 1 else "rounds"
    return f"{attempts} {rounds} of automated fixes did not resolve it"


def post_human_escalation(
    topic: str, goal_id: Optional[str], file_name: str, attempts: int
) -> None:
    """Post the terminal escalation to the feature board. Best-effort: a board that is
    unreachable must never turn a clean stop into a crash."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_messages import post_message

        post_message(
            get_db(),
            board="feature",
            scope=topic,
            from_agent="system",
            to_agent="human",
            type="escalation",
            text=(
                f"Human checkpoint required — {file_name} "
                f"({escalation_reason(attempts, file_name)})\n\n"
                "This run uses the compiled-flow executor, which does not support "
                "pause/resume: resolve the feedback file, then re-run the flow from "
                "the start (it will find the file already resolved)."
            ),
            goal_id=goal_id or None,
        )
    except Exception as exc:
        logger.warning("compiled_flow human escalation post failed: %s", exc)
