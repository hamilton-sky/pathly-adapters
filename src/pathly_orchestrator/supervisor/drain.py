"""ONE call site for draining a DAG frontier through ``scheduler_loop``.

Two callers drive the frontier loop, and before this module they each carried their own
copy of the same scaffolding — create a cost tracker, wrap ``spawn_fn`` with it, OR
``tracker.exceeded()`` into an abort predicate, call ``scheduler_loop``:

* ``fan_out._drain`` — an FSM stage that declares ``parallel_states`` (Phase C/D).
* ``goal_executor._run_loop`` — the ``executor: loop`` goal drain.

Duplicated scaffolding is how the two paths drift: a fix to one (the cost cap folding into
``abort_check``, say) silently misses the other. They now share this, so there is a single
place where "drain these ready tasks" is expressed.

What deliberately stays with the CALLERS, because it genuinely differs:

* **isolation** — a stage resolves it from its flow YAML; a goal loop picks its own.
* **the abort predicate** — the FSM watches ``state._abort_flag``; the goal loop watches
  whether it still holds the board lock. The cost cap is NOT part of that difference and is
  folded in here, so neither caller can forget it.
* **the result shape** — a stage merges into the single-spawn dict the FSM loop expects; a
  goal run keeps the raw drain plus its own ``verify_clean_drain``.

This is a convergence step toward one engine, not the retirement of one. ``executor: loop``
remains a distinct product from ``executor: team`` — a flat, gate-less drain versus the full
reviewed pipeline — and collapsing those is a product decision, not a refactor.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional, Tuple

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .cost_cap import CostCapTracker


def drain_frontier(
    state,
    board: str,
    scope: str,
    *,
    isolation,
    spawn_fn: Optional[Callable] = None,
    abort_check: Optional[Callable[[], bool]] = None,
    broadcast_fn: Optional[Callable] = None,
    event_broadcast_fn: Optional[Callable] = None,
    goal_id: Optional[str] = None,
    tracker=None,
) -> Tuple[dict, "CostCapTracker"]:
    """Drain ``(board, scope)``'s ready frontier. Returns ``(raw_result, tracker)``.

    ``raw_result`` is ``scheduler_loop``'s own dict (``completed``/``failed``/``blocked``/
    ``deadlocked``) — unmerged, so each caller can shape it for its own consumer.

    ``tracker`` is the ``CostCapTracker`` that accumulated the drain's real spend: passed in
    when the caller needs it for its own reporting, created here otherwise. It is returned
    either way so the caller can read ``.total`` or call ``.report(...)`` without a second
    accumulator.

    ``spawn_fn`` is wrapped with the tracker here — never wrap it before calling, or each
    task's cost is counted twice. ``abort_check`` supplies only the caller's OWN reason to
    stop; ``tracker.exceeded()`` is OR-ed in, so the cost cap applies to every drain by
    construction rather than by each caller remembering it.
    """
    from pathly_orchestrator.supervisor.cost_cap import init_cost_tracker
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    if tracker is None:
        tracker = init_cost_tracker()

    def _abort() -> bool:
        if abort_check is not None:
            try:
                if abort_check():
                    return True
            except Exception:
                # A caller's abort predicate that raises must not strand the drain; treat
                # it as "no abort signal" and let the cost cap still have its say.
                pass
        return bool(tracker.exceeded())

    raw = scheduler_loop(
        state,
        board,
        scope,
        isolation=isolation,
        broadcast_fn=broadcast_fn,
        event_broadcast_fn=event_broadcast_fn,
        spawn_fn=tracker.wrap(spawn_fn),
        abort_check=_abort,
        goal_id=goal_id,
    )
    return (raw if isinstance(raw, dict) else {"result": raw}), tracker
