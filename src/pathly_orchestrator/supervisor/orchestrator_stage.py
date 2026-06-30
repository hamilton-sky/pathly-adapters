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
            with _lock:
                state.error_kind = "subprocess"
                _set_status(state, "error", broadcast_fn)
            _broadcast(
                {
                    "type": "RUNNER_ERROR",
                    "topic": topic,
                    "message": str(exc),
                    "kind": "subprocess",
                }
            )
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
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    }
                )
                return None

            return decision_result

        # ── Blocked / feedback ────────────────────────────────────────────────
        if result.get("blocked"):
            target = result.get("target_agent", "")
            file_ = result.get("file", "")

            if target == "human":
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"Human checkpoint required: {file_}",
                        "kind": "subprocess",
                    }
                )
                return None

            feedback_rounds += 1
            if feedback_rounds > MAX_FEEDBACK_ROUNDS:
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file_}",
                        "kind": "subprocess",
                    }
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
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    }
                )
                return None

            resolved = [file_]
            continue

        return result
