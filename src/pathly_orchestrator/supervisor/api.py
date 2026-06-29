"""Public API: start/pause/resume/abort/supply_decision/supply_agent_answer/reroute."""

from __future__ import annotations

import secrets
import threading
from typing import Callable, Optional

from .state import RunnerState, logger
from .registry import _lock, _registry, _write_mirror


def start_run(
    topic: str,
    flow: str,
    project_root: str,
    model: str = "claude-sonnet-4-6",
    timeout: int = 600,
    max_iterations: int = 10,
    max_cost_usd: float = 1.0,
    autonomy: Optional[dict] = None,
    broadcast_fn: Optional[Callable] = None,
    interactive: bool = True,
    goal_id: str = "",
    on_done: Optional[Callable] = None,
) -> RunnerState:
    """Start a new supervised run for *topic*.  Raises ValueError if already active.

    goal_id: when set, this run is a goal decompose/executor — the terminal planner
        stage is told to seed THIS goal's DAG (see orchestrator._decompose_directive).
    on_done: called as ``on_done(run_id, result)`` exactly once when the run reaches a
        terminal status (done/error/aborted). ``result`` carries ``status`` and, on
        failure, ``error`` — so a caller (e.g. the decompose lifecycle poster) can clear
        a "running" UI indicator that would otherwise hang forever when _loop errors out.
    """
    import uuid as _uuid

    with _lock:
        existing = _registry.get(topic)
        if existing and existing.status in {"running", "paused", "awaiting_decision"}:
            raise ValueError(
                f"Run for topic {topic!r} is already active (status={existing.status})"
            )

        state = RunnerState(
            topic=topic,
            flow=flow,
            project_root=project_root,
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=max_cost_usd,
            autonomy=autonomy or {},
            run_id=str(_uuid.uuid4()),
            _broadcast_fn=broadcast_fn,
            interactive=interactive,
            goal_id=goal_id,
        )
        state.trace_id = secrets.token_hex(16)
        _registry[topic] = state
        state.status = "running"
        _write_mirror(state)

    if broadcast_fn:
        try:
            broadcast_fn(
                topic,
                {
                    "type": "RUN_STARTED",
                    "topic": topic,
                    "run_id": state.run_id,
                },
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)

    from .orchestrator import _loop

    def _run_and_finalize() -> None:
        # The loop owns all status transitions; we only OBSERVE the terminal status and
        # fire on_done once, so a decompose/goal run always reports completion even when
        # _loop returns via an error path (otherwise the board's timer never stops).
        try:
            _loop(state, broadcast_fn)
        finally:
            if on_done is not None:
                result: dict[str, object] = {"status": state.status}
                if state.status in {"error", "aborted"}:
                    result["error"] = state.error_kind or state.status
                    result["announced"] = state.stop_announced
                try:
                    on_done(state.run_id, result)
                except Exception:
                    logger.warning("on_done callback error", exc_info=True)

    t = threading.Thread(
        target=_run_and_finalize,
        daemon=True,
        name=f"supervisor-{topic}",
    )
    t.start()
    return state


def pause_run(topic: str) -> None:
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._pause_flag = True


def resume_run(topic: str) -> None:
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._pause_flag = False


def abort_run(topic: str, *, announced: bool = False) -> None:
    """Hard-kill the in-flight subprocess (if any) and set status=aborted.

    announced: set True when the caller has already posted a user-facing "stopped"
        message (the ■ Stop route does). The run's on_done reads this and stays quiet
        so the stop isn't announced twice. A killed runner tab leaves it False, so
        on_done becomes the sole announcer that clears the board's timer pill.
    """
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._abort_flag = True
        # Monotonic: once the ■ Stop route announces a stop, a follow-up abort (e.g. the
        # TERMINAL_SIGNAL → frontend kill → user_initiated terminal/result cascade) must
        # not reset it back to un-announced, or on_done would announce the same stop twice.
        state.stop_announced = announced or state.stop_announced
        proc = state._proc
        active_tab_id = state.active_tab_id
        run_id = state.run_id
        broadcast_fn = state._broadcast_fn

    if proc is not None:
        try:
            proc.kill()
        except Exception:
            pass

    if active_tab_id and broadcast_fn:
        try:
            broadcast_fn(
                topic,
                {
                    "type": "TERMINAL_SIGNAL",
                    "topic": topic,
                    "signal": "term",
                    "tab_id": active_tab_id,
                    "run_id": run_id,
                },
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)


def supply_decision(topic: str, decision: str) -> None:
    """Supply a decision for an awaiting_decision run."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        if state.status != "awaiting_decision":
            raise ValueError(
                f"Topic {topic!r} is not awaiting a decision (status={state.status})"
            )
        state._decision = decision
        state._decision_event.set()


def supply_agent_answer(topic: str, answer: str) -> None:
    """Supply a user answer for a stage that asked a question (denied AskUserQuestion)."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        if not state._awaiting_agent_answer:
            raise ValueError(f"Topic {topic!r} is not awaiting an agent answer")
        state._agent_question_answer = answer
        state._agent_question_event.set()


def reroute_run(topic: str, adapter: str) -> None:
    """Override the adapter for the next stage only."""
    with _lock:
        state = _registry.get(topic)
        if state is None:
            raise KeyError(topic)
        state._reroute_adapter = adapter
