"""Ground-truth check for a goal that just drained its whole task-DAG.

``fsm/gates/command.py`` closed the self-report hole for the LINEAR pipeline (team /
team-build): a builder writing ``RESULT: PASS`` no longer advances the flow on its own
say-so. The loop executor's DAG had no equivalent — ``scheduler.py`` decides success from
each task's own ``outcome`` dict alone (see ``_outcome_is_failure``), so a goal could drain
every task "successfully" over code that does not build.

This module runs the SAME ``verify.build`` / ``verify.test`` commands the FSM path uses,
once, at goal-drain — not per task, which would run the whole suite N times for one goal.
It reuses ``fsm.gates.command.check_command_gate`` directly rather than re-implementing
command resolution / clipping / event-writing, so both call sites share one behavior.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("pathly.goal_verify")

# Mirrors team.flow.yaml's two command_gate checkpoints (BUILDING->REVIEWING,
# TESTING->RETRO), collapsed into one because the loop executor has no BUILDING/TESTING
# split — a goal's tasks interleave both kinds of work.
_CHECKS = (("build", "BUILD_FAILURES.md"), ("test", "TEST_FAILURES.md"))


def verify_goal_completion(goal_dir: str) -> dict | None:
    """Run configured verify commands against a goal whose DAG just drained cleanly.

    Returns ``None`` on pass (or when neither ``verify.build`` nor ``verify.test`` is
    configured — the same fail-open contract as the FSM gate, so this is inert until a
    project opts in). Returns ``{"gate", "reason", "feedback_file"}`` on the first failure.
    """
    from pathly_orchestrator.fsm.gates.command import check_command_gate

    storage_path = Path(goal_dir)
    for command_key, on_fail in _CHECKS:
        gate = {"type": "command_gate", "command_key": command_key, "on_fail": on_fail}
        failure = check_command_gate(gate, storage_path, "DRAINING", "DONE")
        if failure is None:
            continue
        feedback_path = storage_path / "feedback" / on_fail
        try:
            reason = feedback_path.read_text(encoding="utf-8")
        except OSError:
            reason = f"verify.{command_key} failed"
        return {
            "gate": command_key,
            "reason": reason[:2000],
            "feedback_file": str(feedback_path),
        }
    return None


def verify_clean_drain(
    res: dict, goal_dir: str | None, board: str, scope: str, goal_id: str
) -> None:
    """Mutate a loop-executor result in place: run the ground-truth check iff the drain
    was unambiguously clean, and turn a failure into the same shape an ``on_done``
    consumer already treats as failed (``res["error"]`` set — see ``goals.py``'s
    ``_on_done``, which reports anything carrying ``error`` as a failed run).

    Skips (no-op) on anything less than a fully clean drain — no resolvable storage dir,
    nothing completed, or any failed/blocked/deadlocked task — so this can never turn an
    aborted or partial run into a false gate failure; that run's own status already
    explains itself.
    """
    if (
        not goal_dir
        or not res.get("completed")
        or res.get("failed")
        or res.get("blocked")
        or res.get("deadlocked")
    ):
        return
    gate_failure = verify_goal_completion(goal_dir)
    if gate_failure is None:
        return
    res["error"] = (
        f"verify.{gate_failure['gate']} failed after the DAG drained — "
        f"see {gate_failure['feedback_file']}"
    )
    res["gate_failed"] = gate_failure["gate"]
    post_gate_failure_escalation(board, scope, goal_id, gate_failure)


def post_gate_failure_escalation(
    board: str, scope: str, goal_id: str, gate_failure: dict
) -> None:
    """Board escalation for a failed goal-level verify — best-effort, never raises.

    The loop executor has no FSM-style feedback routing to re-drive a fix automatically,
    so the failure surfaces where a human (or another agent) will see it: an answerable
    escalation on the goal's own board, the same mechanism a headless human checkpoint
    uses (`orchestrator_stage.py::_post_human_escalation`).
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import post_message

        post_message(
            get_db(),
            board=board,
            scope=scope,
            from_agent="supervisor",
            type="escalation",
            text=(
                f"Goal verification failed (verify.{gate_failure['gate']}) — every task "
                f"reported success, but the project's own {gate_failure['gate']} command did "
                f"not pass:\n\n{gate_failure['reason'][:1500]}"
            ),
            goal_id=goal_id,
        )
    except Exception:
        logger.debug("goal_verify: escalation post failed", exc_info=True)
