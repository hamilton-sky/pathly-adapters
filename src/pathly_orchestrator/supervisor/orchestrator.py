"""Run loop and stage resolution."""

from __future__ import annotations

import secrets
import time
from typing import Callable, Optional

from .interactions import _await_agent_question
from .orchestrator_stage import _resolve_stage_supervised  # noqa: F401
from .registry import _lock, _set_status, _write_mirror
from .state import OpenSession, RunnerState, logger
from .terminal import _write_supervisor_phase_summary

# The terminal stage that seeds a board task-DAG. When a run carries a goal_id (it is a
# decompose/executor of an EXISTING goal), this stage must attach its tasks to that goal
# rather than find-or-create its own — otherwise a "decompose goal X via consultation"
# seeds the wrong goal (or none). Mirrors the directive _decompose_plan injects.
_DAG_SEEDER_AGENT = "planning/plan"


def _decompose_directive(agent: str, goal_id: str) -> str:
    """Return the 'seed THIS goal' instruction suffix, or '' when it doesn't apply."""
    if not goal_id or agent != _DAG_SEEDER_AGENT:
        return ""
    return (
        "\n\n## Decompose target\n"
        "This run decomposes an EXISTING goal. Attach EVERY task you post to "
        f"goal_id={goal_id!r} and do NOT post a new goal — it already exists. "
        "Use that goal_id as $GOAL_ID at the 'Post Tasks to Comms Board' step."
    )


def _stage_model_for(adapter: str, model: str) -> str:
    """The model to spawn a stage with, reconciled to that stage's (per-stage) engine.

    A flow's ``adapter_map`` can route one stage to a different engine than the run-level
    ``model`` belongs to — e.g. the consultation flow runs PO_DISCUSSING + DESIGNING on
    ``codex`` while the run model is ``claude-sonnet-4-6``. Spawning that adapter with a
    foreign-engine model hard-crashes the supervisor loop at ``resolve_command``'s mismatch
    guard (``adapter_model_mismatch`` → ``loop_crashed`` → "decomposition failed"). When the
    model doesn't belong to ``adapter``, fall back to that engine's OWN default by returning
    ``""`` (``resolve_command`` then drops the ``--model`` pair). The run-level model is
    returned unchanged whenever it matches — or when the adapter is unconstrained/unknown, so
    a real model is never needlessly dropped.
    """
    from pathly_orchestrator.adapters import validate_adapter_model

    return "" if validate_adapter_model(adapter, model) else model


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

    def _fail(reason: str, message: str) -> None:
        """Terminate the run in error with a SPECIFIC reason (not the old catch-all "subprocess").

        `reason` becomes ``state.error_kind`` → the board's "goal run failed — <reason>" text (via the
        run's on_done), so it must name the real cause: fsm_unreachable / fsm_blocked / spawn_failed /
        no_next_state / loop_crashed. Also surfaced as the RUNNER_ERROR ``kind`` for parity.
        """
        with _lock:
            state.error_kind = reason
            _set_status(state, "error", broadcast_fn)
        _broadcast(
            {"type": "RUNNER_ERROR", "topic": topic, "message": message, "kind": reason}
        )

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
                    {
                        "flow": flow,
                        "topic": topic,
                        "project_root": project_root,
                        "goal_id": state.goal_id or None,
                    }
                )
            except Exception as exc:
                # Belt-and-suspenders: ANY next_action failure (unreachable, socket timeout, or a
                # malformed response) fails the run with a nameable reason instead of bubbling to the
                # whole-loop catch-all and becoming an opaque loop_crashed. fsm_http_client already
                # degrades a slow/timed-out self-call to the in-process path; this is the floor.
                _fail("fsm_unreachable", str(exc))
                return

            if response.get("done"):
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return

            if response.get("blocked"):
                _fail("fsm_blocked", f"FSM blocked: {response.get('file', '')}")
                return

            current_fsm_state = response.get("current_state", "")
            instructions = response.get("instructions", "")
            # Goal decompose/executor: tell the DAG-seeder stage which existing goal to fill.
            instructions += _decompose_directive(
                response.get("agent", ""), state.goal_id
            )
            preferred_adapter = response.get("preferred_adapter", "") or "claude"

            # Apply reroute override if set
            with _lock:
                if state._reroute_adapter:
                    preferred_adapter = state._reroute_adapter
                    state._reroute_adapter = None

            # Co-resolve the per-stage model with the per-stage adapter (see
            # _stage_model_for): a flow's adapter_map can route a stage to a different engine
            # than the run-level model belongs to, which otherwise hard-crashes the loop.
            stage_model = _stage_model_for(preferred_adapter, model)

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
                    stage_model,
                    run_id,
                    broadcast_fn,
                    session=session_id,
                    autonomy=autonomy_for_adapter,
                )
            except RuntimeError as exc:
                _fail("spawn_failed", str(exc))
                return

            # ── Handle agent questions ────────────────────────────────────────
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
                    with _lock:
                        _set_status(state, "aborted", broadcast_fn)
                    return

                with _lock:
                    _set_status(state, "running", broadcast_fn)

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
                    _fail("spawn_failed", str(exc))
                    return

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
            # Per-stage resilience: a stage-level exception fails THIS stage with a nameable,
            # retryable reason instead of bubbling to the whole-loop catch-all (`loop_crashed`),
            # which killed the entire multi-stage run on one flaky stage (e.g. a codex sandbox
            # error mid-review). Applies to EVERY FSM flow — team / consultation / debug /
            # explore / test all drive this loop. The run stops with a clear reason the user can
            # Retry, and the traceback is logged, instead of an opaque crash that loses the rest
            # of the pipeline.
            try:
                result = _resolve_stage_supervised(
                    state, flow, topic, project_root, model, broadcast_fn, fhc
                )
            except Exception as exc:
                logger.exception(
                    "Stage %s raised for topic %s: %s", state.current_state, topic, exc
                )
                _fail("stage_error", f"{state.current_state or 'stage'}: {exc}")
                return

            if result is None:
                return

            if result.get("done"):
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return

            if result.get("blocked"):
                _fail("blocked", f"Blocked: {result.get('file', '')}")
                return

            _write_supervisor_phase_summary(
                project_root=project_root,
                topic=topic,
                stage=state.current_state or "",
                agent="supervisor",
                text=f"{(state.current_state or 'stage').lower()} complete — {preferred_adapter} finished",
                broadcast_fn=broadcast_fn,
            )

            if result.get("next_state"):
                continue

            # complete_stage returned no next_state — not done, not blocked. The FSM had nowhere to
            # go (e.g. a terminal state with no outgoing transition). Fail with a nameable reason
            # instead of the old catch-all "subprocess".
            _fail(
                "no_next_state",
                f"Stage {state.current_state or '?'} resolved with no next state",
            )
            return

    except Exception as exc:
        logger.exception("Supervisor loop crashed for topic %s: %s", topic, exc)
        with _lock:
            state.error_kind = "loop_crashed"
            try:
                _set_status(state, "error", broadcast_fn)
            except Exception:
                pass
