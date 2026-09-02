"""Fan-out execution for ONE FSM state — the DAG scheduler as a stage executor.

``scheduler_loop`` was wired as a rival ENGINE: ``goal_executor._run_loop`` calls it
top-level, as a peer of ``orchestrator._loop``. This module makes it the fan-out executor
*of a state* instead, which is what turns two engines into one:

    next_action() -> current_state = "BUILDING"
          |
          +- NOT parallel --> spawn one agent          (today, unchanged)
          |
          +- parallel ------> scheduler_loop(...)      <- the fan-out
          |                     returns when the frontier is drained
          v
    run_gates(BUILDING -> REVIEWING)   <- the JOIN. Unchanged: ONE gate run, after
          |                               every worker finished. Not called here.
          v
    complete_stage() -> write_state("REVIEWING")

``fsm_state.current`` stays the scalar ``"BUILDING"`` for the whole drain — the FSM keeps
ownership of flow, states, gates and transitions; the scheduler owns only "run these N
ready tasks". The parallelism lives inside a state's *execution*, not in the state
vocabulary, so ``write_state``'s legality check, the ``STATE.json`` export, the ``pathly-*``
CLI and Studio's flow editor are all untouched.

**Phase C pins ``SerialIsolation`` regardless of what the YAML asks for**, so a parallel
state still drains one task at a time and behaviour is byte-identical to today. Turning
concurrency on is Phase D — the single swap to ``LaneIsolation`` — and it is deliberately
NOT in this change, so a regression is attributable to the architecture move or to the
behaviour change, never to both at once.

See: pathly/features/fsm-fan-out/SPEC.md
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

logger = logging.getLogger("pathly.fan_out")


def load_flow_config(flow_name: str, project_root: str) -> dict:
    """The flow's own dict, or ``{}`` when it cannot be loaded.

    ``{}`` answers ``parallel_config`` with ``None`` -> the single-spawn path, i.e. today's
    exact behaviour. So a flow that fails to load degrades the loop to its pre-fan-out
    self rather than failing a run that never needed the flow dict before this.
    """
    try:
        from pathly_orchestrator.fsm_ops import _load_flow

        config = _load_flow(flow_name, project_root)
        return config if isinstance(config, dict) else {}
    except Exception:
        logger.debug("fan_out: could not load flow %r", flow_name, exc_info=True)
        return {}


def parallel_config(flow_config: dict, state_name: str) -> Optional[dict]:
    """The state's ``parallel_states`` entry, or ``None``.

    ``None`` means today's single spawn — the answer for every state of every packaged
    flow, since none declares ``parallel_states`` (Phase B). A bodiless YAML entry
    (``BUILDING:`` -> ``None``) is a real opt-in with all defaults, hence ``{}`` rather
    than ``None``: the two must not collapse.
    """
    states = (flow_config or {}).get("parallel_states")
    if not isinstance(states, dict) or state_name not in states:
        return None
    entry = states[state_name]
    return dict(entry) if isinstance(entry, dict) else {}


def _resolve_isolation(
    config: dict, state_name: str, board: str, scope: str, goal_id: Optional[str]
):
    """The isolation this state drains with (Phase D — parallelism is on, but gated).

    ``serial`` is obeyed literally. ``worktree`` is legal vocabulary whose implementation
    is still a stub (``WorktreeIsolation`` raises ``NotImplementedError``), so it degrades
    to serial with a warning rather than crashing a run.

    ``lane`` — the default — returns ``AuditedLaneIsolation``: real lane parallelism, but
    only for as long as the frontier's lane partition actually audits safe, re-checked
    every scheduling round. On today's DAGs (no declared footprints) that audits UNSAFE
    and the drain stays serial, which is the correct answer, not a failure: the swap can
    never be worse than Phase C's behaviour, and becomes parallel exactly when a planner
    has declared lanes and footprints that hold up.
    """
    from pathly_orchestrator.supervisor.isolation import SerialIsolation

    requested = config.get("isolation") or "lane"
    if requested == "serial":
        return SerialIsolation()
    if requested == "worktree":
        logger.warning(
            "fan_out: state %s asks for isolation='worktree', which is still a stub — "
            "draining serially instead.",
            state_name,
        )
        return SerialIsolation()

    from pathly_orchestrator.supervisor.lane_partition import AuditedLaneIsolation

    max_workers = config.get("max_workers")
    return AuditedLaneIsolation(
        board,
        scope,
        goal_id,
        max_workers=max_workers if isinstance(max_workers, int) else None,
    )


def _merge_drain_result(drained: dict, cost_usd: float) -> dict:
    """Fold a ``scheduler_loop`` result into the shape a single spawn returns.

    ``_loop``'s downstream handling reads ``cost_usd`` / ``session_id`` /
    ``_outcome_is_failure``, so returning that exact shape is what keeps the orchestrator
    untouched below the call site.

    ``session_id`` is **None by construction**: a fan-out cannot carry one CLI session
    across N agents, and threading one through would corrupt context the moment Phase D
    lets two workers run at once. The FSM loop treats that as "open a new session next
    stage", which is correct here.

    ``outcome="failed"`` when tasks ESCALATED (retries exhausted — ``task_retry``) or
    DEADLOCKED (an unsatisfiable ``depends_on``; the frontier can never drain). Both mean
    the stage did not finish its work. It is deliberately not fatal to the stage: the join
    is ``require_tasks_done``, which blocks the transition on exactly these tasks, and the
    plain-failure path already reports a self-reported failure as a RUNNER_WARNING while
    letting the gate decide. "Frontier drained, these escalated" is the honest report.
    """
    escalated = list(drained.get("failed") or [])
    deadlocked = list(drained.get("deadlocked") or [])
    completed = list(drained.get("completed") or [])
    merged: dict = {
        "cost_usd": cost_usd,
        "session_id": None,
        "outcome": "failed" if (escalated or deadlocked) else "success",
        "result": {
            "fan_out": True,
            "completed": completed,
            "failed": escalated,
            "blocked": list(drained.get("blocked") or []),
            "deadlocked": deadlocked,
        },
    }
    if escalated or deadlocked:
        merged["error"] = (
            f"fan-out drained with {len(escalated)} escalated and "
            f"{len(deadlocked)} deadlocked task(s) "
            f"({len(completed)} completed) — require_tasks_done will block the transition"
        )
    return merged


def _drain(
    state,
    config: dict,
    state_name: str,
    broadcast_fn: Optional[Callable],
    autonomy: bool,
) -> dict:
    """Drain this state's ready tasks through ``scheduler_loop`` and merge the result."""
    import pathly_orchestrator.supervisor as _sup
    from pathly_orchestrator.supervisor.cost_cap import init_cost_tracker
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    # The frontier's (board, scope) must be the SAME pair require_tasks_done counts, or the
    # fan-out and the join would disagree about which tasks belong to this stage.
    # orchestrator_stage.py posts complete_stage with board="feature", scope=topic.
    board, scope = "feature", state.topic
    goal_id = getattr(state, "goal_id", "") or None
    tracker = init_cost_tracker()

    def _spawn(task_state, instructions, adapter, model, task_run_id, task_broadcast):
        # session=None: see _merge_drain_result. autonomy is threaded from the FSM stage so
        # a fan-out worker gets the same permission posture as the single spawn it replaces.
        return _sup._run_stage_via_terminal(
            task_state,
            instructions,
            adapter,
            model,
            task_run_id,
            task_broadcast,
            session=None,
            autonomy=autonomy,
        )

    def _abort_check() -> bool:
        # The FSM's own abort, plus the goal cost cap — folded into the SAME hook
        # scheduler_loop already polls before scheduling anything new (cost_cap.py).
        return bool(getattr(state, "_abort_flag", False)) or tracker.exceeded()

    drained = scheduler_loop(
        state,
        board,
        scope,
        isolation=_resolve_isolation(config, state_name, board, scope, goal_id),
        broadcast_fn=broadcast_fn,
        spawn_fn=tracker.wrap(_spawn),
        abort_check=_abort_check,
        goal_id=goal_id,
    )
    merged = _merge_drain_result(drained, tracker.total)
    tracker.report(merged)  # stamps error/cost_cap_exceeded when the cap was breached
    return merged


def run_stage(
    state,
    flow_config: dict,
    state_name: str,
    instructions: str,
    adapter: str,
    model: str,
    run_id: str,
    broadcast_fn: Optional[Callable],
    *,
    session: Optional[str] = None,
    autonomy: bool = True,
) -> dict:
    """ONE call site for executing an FSM stage.

    No ``parallel_states`` entry -> delegates to ``_run_stage_via_terminal`` with the
    identical arguments, so the single-spawn path is byte-for-byte what it was.
    Entry present -> drains the state's ready tasks and returns a merged result in the
    SAME shape, so ``_loop``'s downstream handling is untouched.

    Gates are NOT run here — ``_loop`` already runs them at the transition, and that is
    the join.
    """
    import pathly_orchestrator.supervisor as _sup

    config = parallel_config(flow_config, state_name)
    if config is None:
        return _sup._run_stage_via_terminal(
            state,
            instructions,
            adapter,
            model,
            run_id,
            broadcast_fn,
            session=session,
            autonomy=autonomy,
        )
    return _drain(state, config, state_name, broadcast_fn, autonomy)
