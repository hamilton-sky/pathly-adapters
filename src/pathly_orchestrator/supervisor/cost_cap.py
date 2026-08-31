"""Aggregate cost-cap enforcement for goal executors — a gap `scheduler.py` has none of.

The FSM loop (`orchestrator.py`) already refuses to spawn a new stage once
`cost_usd_so_far >= max_cost_usd`. The DAG/loop executor (`scheduler.py`) has NO
equivalent: a goal's task-DAG can run to any cost, spawning task after task with
nothing watching the total. This closes that gap WITHOUT touching `scheduler.py`
(frozen at its 400-line ratchet ceiling — extend by adding a file, not growing it):
it wraps whatever `spawn_fn` a goal executor would otherwise pass in to accumulate
real cost as it becomes known, and folds the cap into the SAME `abort_check` hook
`scheduler_loop` already polls at the top of its frontier loop before scheduling
anything new.

Like every stage's cost, this is known only AFTER a task's spawn returns — there is
no incremental cost visibility for a headless `claude -p --output-format json` spawn
(one JSON envelope at process exit, not a stream). So this stops the DAG from
scheduling FURTHER tasks once the aggregate is blown; it cannot preempt one already
in flight, the same limitation the FSM loop's own cap already has.

Fail-open when unconfigured, same contract as `command_gate`: no `goal.max_cost_usd`
setting means no cap, not a blocked run.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional


def resolve_goal_max_cost_usd() -> Optional[float]:
    """Read the ``goal.max_cost_usd`` app-setting. Absent/invalid/non-positive -> None."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), "goal.max_cost_usd", None)
    except Exception:
        return None
    try:
        value = float(raw) if raw else None
    except (TypeError, ValueError):
        return None
    return value if value and value > 0 else None


class CostCapTracker:
    """Accumulates real spend across a goal's tasks and reports a cap breach.

    Thread-safe on the write side (`wrap`'s inner spawn runs in `scheduler.py`'s
    per-task worker threads) even though today's only caller (`SerialIsolation`) runs
    one task at a time — a future `LaneIsolation` goal would make this a real race
    otherwise, and the lock costs nothing while it isn't.
    """

    def __init__(self, max_cost_usd: Optional[float]) -> None:
        self._max = max_cost_usd
        self._lock = threading.Lock()
        self._total = 0.0

    def wrap(self, spawn_fn: Optional[Callable]) -> Callable:
        """Return a spawn_fn with the SAME signature `scheduler.py`'s `_worker` calls,
        feeding this tracker from each task's `cost_usd` before returning the outcome
        unchanged. Resolves the SAME default `scheduler_loop` would (`_run_stage_via_terminal`)
        when `spawn_fn` is None, so callers always get a wrapped, cap-tracked spawn.
        """
        if spawn_fn is None:
            import pathly_orchestrator.supervisor as _sup

            spawn_fn = _sup._run_stage_via_terminal

        def _spawn(state, instructions, adapter, model, task_run_id, broadcast_fn):
            outcome = spawn_fn(
                state, instructions, adapter, model, task_run_id, broadcast_fn
            )
            cost = (
                float(outcome.get("cost_usd") or 0.0)
                if isinstance(outcome, dict)
                else 0.0
            )
            if cost:
                with self._lock:
                    self._total += cost
            return outcome

        return _spawn

    def exceeded(self) -> bool:
        return self._max is not None and self._total >= self._max

    def report(self, res: dict) -> None:
        """Mark *res* as failed (the shape every on_done consumer already checks — see
        goal_verify.verify_clean_drain's identical convention) when the cap was breached.
        """
        if not self.exceeded():
            return
        res["error"] = (
            f"goal cost cap exceeded: spent ${self._total:.4f} >= configured limit "
            f"${self._max:.4f} (app-setting goal.max_cost_usd) — no further tasks were scheduled"
        )
        res["cost_cap_exceeded"] = True


def init_cost_tracker() -> CostCapTracker:
    return CostCapTracker(resolve_goal_max_cost_usd())
