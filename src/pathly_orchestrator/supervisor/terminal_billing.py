"""Per-spawn telemetry and billing reconciliation.

These were closures inside ``_run_stage_via_terminal``; they capture nothing but
``state`` / ``run_id`` / ``model``, so lifting them out costs three explicit parameters and
buys a spawn function that reads as one story instead of three.

Both are best-effort by contract: neither may raise into the spawn path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .state import RunnerState, logger
from .terminal_identity import _run_board_scope


def _emit_executor_telemetry(
    state: RunnerState, run_id: str, ad: Optional[dict], wall: float
) -> None:
    """Project this spawn's result into otel_spans — but ONLY for executor-owned
    runs (board/single/loop), which register no topic RunnerState. FSM/team leave
    executor_owned_telemetry False and are covered by api_lifecycle's span writer.
    Each task gets a fresh span under the goal's trace (goal=trace, task=span).

    The agent_invocation row is NOT written here: executor runs emit an AGENT_DONE
    event, and the universal projector (``invocation_projection`` via
    ``append_event``) derives the invocation from that event stream (folding the
    superseding BILLING_UPDATE). Writing one here too would double-count — hence
    ``write_invocation=False``. Best-effort."""
    if not getattr(state, "executor_owned_telemetry", False):
        return
    try:
        from pathly_orchestrator.runner.telemetry import project_agent_done

        project_agent_done(
            project_root=state.project_root,
            feature=state.topic,
            agent_done=ad,
            run_id=run_id,
            stage=state.current_state or "task",
            agent_role=(ad or {}).get("agent") or "",
            scope_tier=getattr(state, "scope_tier", "feature"),
            trace_id=getattr(state, "goal_trace_id", ""),
            parent_span_id=getattr(state, "goal_span_id", ""),
            wall_seconds=wall,
            write_invocation=False,
        )
    except Exception:
        logger.debug("_emit_executor_telemetry skipped", exc_info=True)


def _reconcile_billing_now(
    state: RunnerState, run_id: str, model: str, data: Optional[dict]
) -> None:
    """Patch the last AGENT_DONE with the REAL CLI cost/tokens from a PTY result.

    The 'pty_result' and slow paths (the PTY reports its result before/without early-advance
    detecting AGENT_DONE — the common case for a fast headless stage) otherwise emit NO
    BILLING_UPDATE, so the DB keeps only the completion-report's subagent-token self-estimate
    — which is $0 for a stage that spawns no subagents (e.g. project-decompose/planner). This
    restores the real-cost capture the invocation-projection refactor dropped from these paths
    (early-advance is covered by _reconciliation_window). Best-effort; never raises into the loop.
    """
    billing = (data or {}).get("result") or {}
    if not isinstance(billing, dict):
        return
    try:
        cost = float(billing.get("cost_usd") or 0.0)
        tokens_in = int(billing.get("tokens_in") or 0)
        tokens_out = int(billing.get("tokens_out") or 0)
        tool_uses = int(billing.get("tool_uses") or 0)
        wall = int((data or {}).get("wall_seconds") or 0)
    except (TypeError, ValueError):
        return
    # Nothing real to add → skip; a 0/0 update would only restate the self-estimate.
    if cost <= 0 and (tokens_in + tokens_out) <= 0:
        return
    try:
        from pathly_orchestrator.fsm_ops import _resolve_storage_path
        from pathly_orchestrator.runner import _patch_last_agent_done

        storage = (
            Path(state.storage_path)
            if state.storage_path
            else _resolve_storage_path(None, state.project_root, state.topic)
        )
        _patch_last_agent_done(
            storage,
            cost,
            tokens_in,
            tokens_out,
            wall,
            tool_uses,
            model=model,
            run_id=run_id,
            board_scope=_run_board_scope(state, storage),
        )
    except Exception as exc:
        logger.warning("_reconcile_billing_now: patch failed: %s", exc)
