"""Stage resolution: the complete_stage feedback loop for a single agent stage."""

from __future__ import annotations

import time
from typing import Callable, Optional

from .registry import _lock, _set_status
from .state import MAX_FEEDBACK_ROUNDS, RunnerState, logger


def _resolve_stage_supervised(
    state: RunnerState,
    flow: str,
    topic: str,
    project_root: str,
    model: str,
    broadcast_fn: Optional[Callable],
    fhc,
) -> Optional[dict]:
    """Run the complete_stage feedback loop without blocking input().

    Returns a result dict (done/next_state/blocked), or None if the loop
    was aborted or errored during this phase.
    """
    import pathly_orchestrator.supervisor as _sup

    _run_stage_via_terminal = _sup._run_stage_via_terminal

    resolved: list[str] = []
    feedback_rounds = 0

    def _broadcast(payload: dict) -> None:
        if broadcast_fn:
            try:
                broadcast_fn(topic, payload)
            except Exception as exc:
                logger.warning("broadcast_fn error: %s", exc)

    def _fail(reason: str, message: str) -> None:
        """Terminate the stage in error with a SPECIFIC reason (not the catch-all "subprocess").

        `reason` becomes ``state.error_kind`` → the board's "goal run failed — <reason>" text:
        fsm_unreachable / human_checkpoint / feedback_exhausted / spawn_failed.
        """
        with _lock:
            state.error_kind = reason
            _set_status(state, "error", broadcast_fn)
        _broadcast(
            {"type": "RUNNER_ERROR", "topic": topic, "message": message, "kind": reason}
        )

    def _post_human_escalation(file_name: str, res: dict) -> None:
        """Surface a headless human-checkpoint on the board as an answerable escalation.

        Otherwise a human gate just fails the run silently and writes a feedback file nobody
        sees. Best-effort (never blocks the still-failing run) and layer-legal — the supervisor
        posts directly via db.comms_messages. Uses the question text the FSM already put in the
        result, so no feedback-file read is needed.
        """
        try:
            from pathly_orchestrator.db.connection import get_db
            from pathly_orchestrator.db.queries.comms_messages import post_message

            content = res.get("instructions") or res.get("message") or ""
            body = f"Human checkpoint required — {file_name}"
            if content:
                body += f"\n\n{content}"
            post_message(
                get_db(),
                board="feature",
                scope=topic,
                from_agent="system",
                to_agent="human",
                type="escalation",
                text=body,
                goal_id=state.goal_id or None,
            )
        except Exception as exc:
            logger.warning("human escalation post failed: %s", exc)

    while True:
        # Abort check before each FSM call
        with _lock:
            if state._abort_flag:
                _set_status(state, "aborted", broadcast_fn)
                return None

        try:
            result = fhc.complete_stage(
                {
                    "flow": flow,
                    "topic": topic,
                    "project_root": project_root,
                    "resolved_files": resolved or None,
                    "board": "feature",
                    "scope": topic,
                    "goal_id": state.goal_id or None,
                }
            )
        except RuntimeError as exc:
            _fail("fsm_unreachable", str(exc))
            return None

        resolved = []

        if result.get("done") or result.get("next_state"):
            return result

        # ── Decision point ────────────────────────────────────────────────────
        if result.get("decide"):
            menu = {
                "question": result.get("question", ""),
                "options": result.get("options", {}),
                "default": result.get("default", ""),
            }
            with _lock:
                state.pending_menu = menu
                _set_status(state, "awaiting_decision", broadcast_fn)
                state._decision = None
                state._decision_event.clear()

            _broadcast({"type": "DECISION_MENU", "topic": topic, "menu": menu})

            # Wait for a decision to be supplied
            while True:
                with _lock:
                    if state._abort_flag:
                        _set_status(state, "aborted", broadcast_fn)
                        return None
                    decision = state._decision
                if decision is not None:
                    break
                time.sleep(0.05)

            with _lock:
                state.pending_menu = None
                state._decision = None
                _set_status(state, "running", broadcast_fn)

            # Feed decision to FSM
            try:
                decision_result = fhc.complete_stage(
                    {
                        "flow": flow,
                        "topic": topic,
                        "project_root": project_root,
                        "decision": decision,
                        "board": "feature",
                        "scope": topic,
                        "goal_id": state.goal_id or None,
                    }
                )
            except RuntimeError as exc:
                _fail("fsm_unreachable", str(exc))
                return None

            return decision_result

        # ── Blocked / feedback ────────────────────────────────────────────────
        if result.get("blocked"):
            target = result.get("target_agent", "")
            file_ = result.get("file", "")

            if target == "human":
                _post_human_escalation(file_, result)
                _fail("human_checkpoint", f"Human checkpoint required: {file_}")
                return None

            feedback_rounds += 1
            if feedback_rounds > MAX_FEEDBACK_ROUNDS:
                _fail(
                    "feedback_exhausted",
                    f"Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file_}",
                )
                return None

            fb_instructions = result.get(
                "instructions", f"Resolve feedback in feedback/{file_}"
            )

            with _lock:
                if state._abort_flag:
                    _set_status(state, "aborted", broadcast_fn)
                    return None
                autonomy_for_adapter = state.autonomy.get(state.current_adapter, True)

            fb_run_id = f"{topic}-fb{feedback_rounds}-{int(time.time() * 1000)}"
            try:
                _run_stage_via_terminal(
                    state,
                    fb_instructions,
                    state.current_adapter or "claude",
                    model,
                    fb_run_id,
                    broadcast_fn,
                    session=None,
                    autonomy=autonomy_for_adapter,
                )
            except RuntimeError as exc:
                _fail("spawn_failed", str(exc))
                return None

            resolved = [file_]
            continue

        return result
