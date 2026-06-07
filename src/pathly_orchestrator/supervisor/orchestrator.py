"""Run loop and stage resolution."""

from __future__ import annotations

import secrets
import time
from typing import Callable, Optional

from .state import RunnerState, OpenSession, MAX_FEEDBACK_ROUNDS, logger
from .registry import _lock, _write_mirror, _set_status
from .interactions import _await_agent_question


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
                # Escalate — surface as error (cannot block waiting for human in headless mode)
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


def _loop(state: RunnerState, broadcast_fn: Optional[Callable]) -> None:
    from pathly_orchestrator import fsm_http_client as fhc
    from pathly_orchestrator.adapters import resolve_command
    import pathly_orchestrator.supervisor as _sup
    _run_stage_via_terminal = _sup._run_stage_via_terminal

    flow = state.flow
    topic = state.topic
    project_root = state.project_root
    model = state.model

    def _broadcast(payload: dict) -> None:
        if broadcast_fn:
            try:
                broadcast_fn(topic, payload)
            except Exception as exc:
                logger.warning("broadcast_fn error: %s", exc)

    try:
        while True:
            # ── Boundary: check abort ──────────────────────────────────────────
            with _lock:
                if state._abort_flag:
                    _set_status(state, "aborted", broadcast_fn)
                    return

            # ── Boundary: check pause ─────────────────────────────────────────
            with _lock:
                if state._pause_flag:
                    _set_status(state, "paused", broadcast_fn)

            while True:
                with _lock:
                    is_paused = state._pause_flag
                    abort_now = state._abort_flag
                if abort_now:
                    with _lock:
                        _set_status(state, "aborted", broadcast_fn)
                    return
                if not is_paused:
                    break
                time.sleep(0.1)

            with _lock:
                _set_status(state, "running", broadcast_fn)

            # ── Boundary: check caps ──────────────────────────────────────────
            with _lock:
                over_iter = state.iterations >= state.max_iterations
                over_cost = state.cost_usd_so_far >= state.max_cost_usd
            if over_iter or over_cost:
                with _lock:
                    state.error_kind = "cap_exceeded"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": "Cap exceeded",
                        "kind": "cap_exceeded",
                    }
                )
                return

            # ── Call FSM next_action ──────────────────────────────────────────
            try:
                response = fhc.next_action(
                    {"flow": flow, "topic": topic, "project_root": project_root}
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
                return

            if response.get("done"):
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return

            if response.get("blocked"):
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"FSM blocked: {response.get('file', '')}",
                        "kind": "subprocess",
                    }
                )
                return

            current_fsm_state = response.get("current_state", "")
            instructions = response.get("instructions", "")
            preferred_adapter = response.get("preferred_adapter", "") or "claude"

            # Apply reroute override if set
            with _lock:
                if state._reroute_adapter:
                    preferred_adapter = state._reroute_adapter
                    state._reroute_adapter = None

            # ── Session continuity ────────────────────────────────────────────
            with _lock:
                open_sess = state.open_session
                autonomy_for_adapter = state.autonomy.get(preferred_adapter, True)

            session_id: Optional[str] = None
            degraded = False

            try:
                cmd_info = resolve_command(preferred_adapter, "", "", autonomy=False)
                adapter_supports_resume = cmd_info["supports_resume"]
            except ValueError:
                adapter_supports_resume = False

            if (
                open_sess is not None
                and open_sess.adapter == preferred_adapter
                and adapter_supports_resume
                and open_sess.session_id
            ):
                session_id = open_sess.session_id
                session_action = "continued"
            else:
                session_id = None
                session_action = "opened"
                if not adapter_supports_resume:
                    degraded = True

            _broadcast(
                {
                    "type": "SESSION",
                    "topic": topic,
                    "adapter": preferred_adapter,
                    "kind": session_action,
                    "degraded": degraded,
                }
            )

            with _lock:
                state.current_state = current_fsm_state
                state.current_adapter = preferred_adapter
                _write_mirror(state)

            _broadcast(
                {
                    "type": "STAGE_CHANGE",
                    "topic": topic,
                    "state": current_fsm_state,
                    "adapter": preferred_adapter,
                    "iteration": state.iterations,
                }
            )

            # ── Invoke agent ──────────────────────────────────────────────────
            run_id = f"{topic}-{state.iterations + 1}-{int(time.time() * 1000)}"
            state.span_id = secrets.token_hex(8)
            try:
                invoke_result = _run_stage_via_terminal(
                    state,
                    instructions,
                    preferred_adapter,
                    model,
                    run_id,
                    broadcast_fn,
                    session=session_id,
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
                return

            # ── Handle agent questions (AskUserQuestion denied in headless mode) ──────
            _MAX_QUESTION_ROUNDS = 3
            for _q_round in range(_MAX_QUESTION_ROUNDS):
                ask_q = (invoke_result or {}).get("ask_user_question")
                if not ask_q:
                    break

                tool_input = ask_q.get("tool_input") or {}
                qs = tool_input.get("questions") or []
                q_text = qs[0].get("question", "") if qs else ""

                answer = _await_agent_question(state, topic, ask_q, broadcast_fn)
                if answer is None:
                    # Aborted while waiting for answer
                    with _lock:
                        _set_status(state, "aborted", broadcast_fn)
                    return

                with _lock:
                    _set_status(state, "running", broadcast_fn)

                # Build retry instructions: prepend the user's answer so the agent
                # continues the stage task with the information it needed
                answer_block = (
                    f"CONTEXT — The user answered your question before you continue:\n"
                    f"Q: {q_text}\n"
                    f"A: {answer}\n\n"
                    f"Now proceed with the original task using this answer.\n\n"
                )
                retry_run_id = f"{run_id}-q{_q_round + 1}"
                retry_session = (invoke_result or {}).get("session_id") or session_id
                try:
                    invoke_result = _run_stage_via_terminal(
                        state,
                        answer_block + instructions,
                        preferred_adapter,
                        model,
                        retry_run_id,
                        broadcast_fn,
                        session=retry_session,
                        autonomy=autonomy_for_adapter,
                    )
                except RuntimeError as exc:
                    with _lock:
                        state.error_kind = "subprocess"
                        _set_status(state, "error", broadcast_fn)
                    _broadcast({
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": str(exc),
                        "kind": "subprocess",
                    })
                    return
            # (end agent-question retry loop)

            # ── Update cost + session from invoke result ───────────────────────
            new_cost = (invoke_result or {}).get("cost_usd", 0.0) or 0.0
            new_session_id = (invoke_result or {}).get("session_id")

            with _lock:
                state.iterations += 1
                state.cost_usd_so_far += new_cost
                state.open_session = OpenSession(
                    adapter=preferred_adapter,
                    session_id=new_session_id or session_id,
                    resumable=adapter_supports_resume,
                )
                _write_mirror(state)

            _broadcast(
                {
                    "type": "COST_UPDATE",
                    "topic": topic,
                    "cost_usd": state.cost_usd_so_far,
                    "iterations": state.iterations,
                    "max_cost_usd": state.max_cost_usd,
                }
            )

            # ── Resolve stage (feedback loop + decide) ────────────────────────
            result = _resolve_stage_supervised(
                state, flow, topic, project_root, model,
                broadcast_fn, fhc
            )

            if result is None:
                # Loop was aborted or errored during resolve
                return

            if result.get("done"):
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return

            if result.get("blocked"):
                with _lock:
                    state.error_kind = "subprocess"
                    _set_status(state, "error", broadcast_fn)
                _broadcast(
                    {
                        "type": "RUNNER_ERROR",
                        "topic": topic,
                        "message": f"Blocked: {result.get('file', '')}",
                        "kind": "subprocess",
                    }
                )
                return

            # next_state — continue loop
            if result.get("next_state"):
                continue

            # Unexpected
            with _lock:
                state.error_kind = "subprocess"
                _set_status(state, "error", broadcast_fn)
            return

    except Exception as exc:
        logger.exception("Supervisor loop crashed for topic %s", topic)
        with _lock:
            state.error_kind = "subprocess"
            try:
                _set_status(state, "error", broadcast_fn)
            except Exception:
                pass
