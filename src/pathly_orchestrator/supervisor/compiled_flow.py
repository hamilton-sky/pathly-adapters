"""Phase 2 of the FSM/DAG convergence — a lightweight direct executor for opted-in flows.

``run_compiled_flow`` walks a flow's ``states``/``transitions`` directly in Python instead
of driving it through ``orchestrator.py``'s ``_loop`` (which advances via ``/next_action``/
``/complete_stage`` HTTP calls into ``fsm_ops.py``, backed by the persisted ``fsm_state``
DB row + ``STATE.json``). This run's position in the flow lives ONLY in this function's
local ``current`` variable, for the lifetime of this call — nothing is written to
``fsm_state``/``STATE.json`` for a compiled-flow run.

It reuses the SAME pure, flow_config+filesystem-only helpers ``fsm_ops_complete.complete_stage``
already orchestrates — ``route_feedback``, ``evaluate_transition_rules``, ``run_gates``,
``run_transition_actions`` — and the SAME prompt-building path (``fsm_compose.build_prompt`` /
``build_prompt_for_agent``), so every composed skill still gets the "you're headless, ignore
the FSM-operations instructions in the body above" runner-contract override.

**Why this exists instead of literally seeding DAG task rows for ``scheduler.py`` to drain**
(the more "complete" convergence): the skills these flows point at (``fix/build.md``,
``debug/build.md``, ``debug/verify.md``) contain literal "call ``pathly-fsm-call
complete-stage``" instructions in their bodies. That is neutralized ONLY by
``fsm_compose.build_prompt``'s injected runner-contract block — the generic DAG-task prompt
path (``compose_skill("development/execute-task", ...)``, what ``scheduler.py``'s real
loop-executor tasks use) does NOT inject it. Reusing that path verbatim for these flows
would leave an agent trying to call an FSM endpoint that means nothing for this run. Building
on ``fsm_compose.build_prompt`` instead sidesteps the landmine entirely, at the cost of not
gaining Phase 1's DAG-native retry/escalation/deadlock machinery (this executor has its own,
much simpler, in-process feedback-round loop instead — the inner "Settle" loop below).

**Opt-in per flow, off by default.** ``resolve_compiled_flows()`` reads the
``flow.compiled_executors`` app-setting (comma-separated flow names) — same fail-open-to-off
contract as ``command_gate``/``cost_cap``/``task_retry``'s own settings: unconfigured or
unparseable means every flow still runs through ``orchestrator.py``'s ``_loop``, unchanged.
Only ``quick-fix`` and ``debug`` have been verified against this executor (no ``gates``, no
``adapter_map``, no ``transition_rules`` at all — every transition is the flow's own listed
default, so ``evaluate_transition_rules`` never returns a ``decide`` block). Adding another
flow to the setting is untested and should not be done without re-verifying its shape first.

**Known, deliberate limitations vs. the FSM path (documented, not silently absorbed):**

- **No park/resume.** A human-checkpoint feedback file (``target_agent == "human"``) FAILS
  the run with a clear reason instead of parking it. A parked run has nowhere to resume
  FROM here (no persisted current-state) — faking "parked" would silently restart the whole
  flow from ``states[0]`` on resume, which is worse than an honest failure. Fine for
  quick-fix/debug (their human checkpoints are the rare/edge-case path per their own
  ``feedback_routing`` comments); a flow that leans on human checkpoints routinely should
  not be added to ``flow.compiled_executors``.
- **No session continuity.** Every stage spawns a fresh session (unlike ``_loop``'s
  same-adapter session reuse). A real, small cost increase; not implemented for this first
  slice.
- **A pre-existing ``fsm_state``/``STATE.json`` row for this topic refuses the run outright**
  (``existing_fsm_state``) rather than silently ignoring prior FSM-driven progress on the
  same topic — this executor has no notion of "resume from state X", so running it against a
  topic that already has FSM progress would otherwise restart from ``states[0]`` unnoticed.
- **A ``decide`` transition rule fails loudly** (``decide_unsupported``) rather than being
  silently mishandled — neither validated flow uses one, so this path exists only to fail
  safe if a flow with one is ever added to the setting without updating this executor first.
- **``escalation_routing`` works, but off IN-MEMORY counts.** The tiers climb off a retry
  count the FSM path reads from ``STATE.json``'s ``retry_count_by_key``; this executor
  writes no ``STATE.json``, so it keeps its own per-file ``retry_by_file`` dict for the
  run's lifetime and passes it through ``route_feedback``'s ``retry_counts=`` seam. Same
  ladder, no persistence — which is sound precisely BECAUSE a compiled run cannot resume:
  there is no second call for a count to survive into. A re-run therefore starts every
  file's ladder at round 1, where an FSM re-run would resume the persisted count.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from .compiled_escalation import escalation_reason, post_human_escalation
from .orchestrator import _stage_model_for
from .registry import _lock, _set_status, _write_mirror
from .state import MAX_FEEDBACK_ROUNDS, RunnerState, logger
from .terminal import _write_supervisor_phase_summary

# Both live in the top-level ``flow_settings`` hub so ``cli/`` can ask "is this flow
# compiled?" without importing the supervisor package (see flow_settings.py). Re-exported
# here because this module is where every existing caller and test looks for them.
from ..flow_settings import is_compiled_flow, resolve_compiled_flows

__all__ = ["is_compiled_flow", "resolve_compiled_flows", "run_compiled_flow"]


def run_compiled_flow(state: RunnerState, broadcast_fn: Optional[Callable]) -> None:
    """Drive ``state.flow`` to completion by walking its states directly. Same external
    contract as ``orchestrator._loop`` (status transitions, broadcasts, abort/pause/cap
    checks) so it is a drop-in alternative for ``api.start_run``'s ``_run_and_finalize``.
    """
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.fsm import (
        evaluate_transition_rules,
        route_feedback,
        run_gates,
        run_transition_actions,
    )
    from pathly_orchestrator.fsm_compose import build_prompt, build_prompt_for_agent
    from pathly_orchestrator.fsm_compose_stage import _resolve_adapter
    from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path
    from pathly_orchestrator.supervisor.scheduler import _outcome_is_failure
    from pathly_orchestrator.supervisor.spawn_policy import effective_model
    import pathly_orchestrator.supervisor as _sup

    _run_stage_via_terminal = _sup._run_stage_via_terminal

    topic = state.topic
    project_root = state.project_root
    model = state.model
    flow_config = _load_flow(state.flow, project_root)
    storage_path = _resolve_storage_path(flow_config, project_root, topic)

    def _broadcast(payload: dict) -> None:
        if broadcast_fn:
            try:
                broadcast_fn(topic, payload)
            except Exception as exc:
                logger.warning("broadcast_fn error: %s", exc)

    def _fail(reason: str, message: str) -> None:
        with _lock:
            state.error_kind = reason
            _set_status(state, "error", broadcast_fn)
        _broadcast(
            {"type": "RUNNER_ERROR", "topic": topic, "message": message, "kind": reason}
        )

    existing = eventlog.read_state(str(storage_path))
    if existing is not None:
        _fail(
            "existing_fsm_state",
            f"{topic} already has FSM state — the compiled executor only runs a topic "
            "from a clean start (it cannot resume from an existing state).",
        )
        return

    current = flow_config["states"][0]
    # Per-FILE retry counts for the run's lifetime, feeding route_feedback's
    # escalation_routing tiers. The FSM path reads these from STATE.json's
    # retry_count_by_key (max across conversations); this executor writes no STATE.json,
    # so without them every round resolved to the base agent — no round-3 specialist
    # hand-off and no round-4 human escalation, on the two flows most likely to loop.
    # Nothing needs persisting to fix that: a compiled run lives entirely inside this
    # call, so an in-memory dict passed through route_feedback's existing `retry_counts`
    # seam gives the identical ladder. Keyed per file and NOT reset per stage, matching
    # _read_retry_counts' "how many times has THIS file failed" semantics.
    retry_by_file: dict[str, int] = {}

    try:
        while True:
            with _lock:
                if state._abort_flag:
                    _set_status(state, "aborted", broadcast_fn)
                    return
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
                over_iter = state.iterations >= state.max_iterations
                over_cost = state.cost_usd_so_far >= state.max_cost_usd
            if over_iter or over_cost:
                _fail("cap_exceeded", "Cap exceeded")
                return

            agent = flow_config["agent_map"][current]
            preferred_adapter = _resolve_adapter(flow_config, current) or "claude"
            with _lock:
                autonomy_for_adapter = state.autonomy.get(preferred_adapter, True)
            stage_model = effective_model(
                agent, preferred_adapter, _stage_model_for(preferred_adapter, model)
            )

            with _lock:
                state.current_state = current
                state.current_adapter = preferred_adapter
                _write_mirror(state)
            _broadcast(
                {
                    "type": "STAGE_CHANGE",
                    "topic": topic,
                    "state": current,
                    "adapter": preferred_adapter,
                    "iteration": state.iterations,
                }
            )

            instructions = build_prompt(
                flow_config, current, storage_path, state.goal_id or ""
            )
            run_id = f"{topic}-{state.iterations + 1}-{int(time.time() * 1000)}"
            try:
                invoke_result = _run_stage_via_terminal(
                    state,
                    instructions,
                    preferred_adapter,
                    stage_model,
                    run_id,
                    broadcast_fn,
                    session=None,
                    autonomy=autonomy_for_adapter,
                )
            except RuntimeError as exc:
                _fail("spawn_failed", str(exc))
                return

            if _outcome_is_failure(invoke_result):
                _reason = (
                    (invoke_result or {}).get("error")
                    or (invoke_result or {}).get("outcome")
                    or "self-reported failure"
                )
                logger.warning(
                    "compiled_flow: stage %s for topic %s self-reported failure (%s) but "
                    "exited cleanly; continuing — downstream feedback routing is the gate",
                    current,
                    topic,
                    _reason,
                )
                _broadcast(
                    {
                        "type": "RUNNER_WARNING",
                        "topic": topic,
                        "message": (
                            f"Stage {current} reported failure ({_reason}) but exited "
                            "cleanly; continuing."
                        ),
                    }
                )

            new_cost = (invoke_result or {}).get("cost_usd", 0.0) or 0.0
            with _lock:
                state.iterations += 1
                state.cost_usd_so_far += new_cost
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

            # ── Settle: resolve feedback + gate failures (may loop several rounds) ──
            feedback_rounds = 0
            next_state: str | dict = ""
            while True:
                with _lock:
                    if state._abort_flag:
                        _set_status(state, "aborted", broadcast_fn)
                        return

                feedback = route_feedback(
                    flow_config, storage_path, retry_counts=retry_by_file
                )
                if feedback is not None:
                    target = feedback["target_agent"]
                    file_ = feedback["file"]
                    if target == "human":
                        attempts = int(feedback.get("retry_count") or 0)
                        post_human_escalation(topic, state.goal_id, file_, attempts)
                        _fail(
                            "human_checkpoint",
                            f"Human checkpoint required: {file_} "
                            f"({escalation_reason(attempts, file_)}; the compiled "
                            "executor does not support park/resume)",
                        )
                        return
                    feedback_rounds += 1
                    if feedback_rounds > MAX_FEEDBACK_ROUNDS:
                        _fail(
                            "feedback_exhausted",
                            f"Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file_}",
                        )
                        return
                    fb_instructions = build_prompt_for_agent(
                        target,
                        storage_path,
                        feedback_file=file_,
                        retry_count=feedback.get("retry_count", 0),
                    )
                    fb_model = effective_model(target, preferred_adapter, model)
                    fb_run_id = f"{topic}-fb{feedback_rounds}-{int(time.time() * 1000)}"
                    try:
                        _run_stage_via_terminal(
                            state,
                            fb_instructions,
                            preferred_adapter,
                            fb_model,
                            fb_run_id,
                            broadcast_fn,
                            session=None,
                            autonomy=autonomy_for_adapter,
                        )
                    except RuntimeError as exc:
                        _fail("spawn_failed", str(exc))
                        return
                    retry_by_file[file_] = retry_by_file.get(file_, 0) + 1
                    continue  # re-check route_feedback

                next_state = evaluate_transition_rules(
                    flow_config,
                    current,
                    storage_path,
                    goal_id=state.goal_id or None,
                    feature_scope=topic,
                )
                if isinstance(next_state, dict):
                    _fail(
                        "decide_unsupported",
                        f"State {current} resolves via a 'decide' rule, which the "
                        "compiled executor does not support",
                    )
                    return

                gate_failure = run_gates(
                    flow_config,
                    current,
                    next_state,
                    storage_path,
                    topic,
                    0,
                    goal_id=state.goal_id or None,
                    feature_scope=topic,
                    board="feature",
                )
                if gate_failure is not None:
                    continue  # gate_failed() wrote a feedback file; re-check route_feedback
                break  # settled: no open feedback, gates passed

            run_transition_actions(
                flow_config,
                current,
                next_state,
                storage_path,
                topic,
                0,
                project_root=project_root or None,
            )
            _write_supervisor_phase_summary(
                project_root=project_root,
                topic=topic,
                stage=current,
                agent="supervisor",
                text=f"{current.lower()} complete — {preferred_adapter} finished",
                broadcast_fn=broadcast_fn,
            )

            if next_state == "DONE":
                with _lock:
                    _set_status(state, "done", broadcast_fn)
                return
            current = next_state

    except Exception as exc:
        logger.exception("compiled_flow loop crashed for topic %s: %s", topic, exc)
        with _lock:
            state.error_kind = "loop_crashed"
            try:
                _set_status(state, "error", broadcast_fn)
            except Exception:
                pass
