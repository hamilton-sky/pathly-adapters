"""What one stage spawn changed: a ``SPAWN_WINDOW`` event per single-path spawn (build-proof).

The floor, scope and reviewer gates must tell who wrote a file. A planner or architect routed a
feedback file may edit ``IMPLEMENTATION_PLAN.md`` while the FSM is still in BUILDING, and a
reviewer may write ``REVIEW.md`` and nothing else. So, for a flow that has one of those gates,
every single-path spawn is wrapped by :func:`observe`, which snapshots the git working tree and
``HEAD`` before and after the spawn and appends

    SPAWN_WINDOW {role, run_id, state, before, after, head_before, head_after}

to the run's event log. ``fsm/gates/_proof.py`` reads the windows back.

Two spawn sites call it, each passing the role explicitly: ``fan_out.run_stage``'s single
spawn (the flow's ``role_map`` entry for the state) and the feedback spawn in
``orchestrator_stage._resolve_stage_supervised`` (the feedback's ``target_agent``).
``terminal_identity._spawn_role`` is not used: it reads the state's agent, so a builder routed
a feedback file inside REVIEWING would be recorded as the reviewer.

Recording never changes the spawn: its result comes back unchanged, an exception from it
propagates (and no window is written), and any snapshot or event failure is logged and
swallowed. Outside a git repo (or when git fails) there is no window at all.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from pathly_orchestrator.proof import tree

logger = logging.getLogger("pathly.spawn_window")

# The gate types that read SPAWN_WINDOW events. A flow without one records none, so a run
# that no gate will judge pays for no snapshot.
WINDOW_GATES = frozenset({"floor_gate", "scope_gate", "reviewer_unchanged"})


def wants_windows(flow_config: Optional[dict]) -> bool:
    """True when any transition in the flow's ``gates`` has a gate that reads windows."""
    gates = (flow_config or {}).get("gates")
    if not isinstance(gates, dict):
        return False
    for entries in gates.values():
        for gate in entries or []:
            if isinstance(gate, dict) and gate.get("type") in WINDOW_GATES:
                return True
    return False


def _take(root: str) -> Optional[tuple[str, Optional[str]]]:
    """``(tree, head)`` for the working tree now, or None (no repo, or git failed)."""
    if not root:
        return None
    try:
        snapshot = tree.snapshot(root)
        if snapshot is None:
            return None
        return snapshot, tree.head(root)
    except Exception:
        logger.warning("spawn_window: snapshot of %s failed", root, exc_info=True)
        return None


def _storage_path(state) -> str:
    """The run's storage dir, resolved the way ``terminal.py`` resolves it."""
    raw = getattr(state, "storage_path", "") or ""
    if raw:
        return str(raw)
    from pathly_orchestrator.fsm_ops import _resolve_storage_path

    return str(
        _resolve_storage_path(
            None,
            getattr(state, "project_root", "") or "",
            getattr(state, "topic", "") or "",
        )
    )


def _record(state, role: str, run_id: str, before: tuple, root: str) -> None:
    """Snapshot again and append the window. Never raises."""
    try:
        after = _take(root)
        if after is None:
            logger.info(
                "spawn_window: no snapshot after run %s in %s, no SPAWN_WINDOW",
                run_id,
                root,
            )
            return
        from pathly_orchestrator import eventlog

        eventlog.append_event(
            _storage_path(state),
            {
                "type": "SPAWN_WINDOW",
                "role": role,
                "run_id": run_id,
                "state": getattr(state, "current_state", "") or "",
                "before": before[0],
                "after": after[0],
                "head_before": before[1],
                "head_after": after[1],
            },
            # DB-backed: never plant a decoy dir that would win _resolve_storage_path's probe.
            create_dir=False,
        )
    except Exception:
        logger.warning("spawn_window: could not record run %s", run_id, exc_info=True)


def observe(
    state,
    flow_config: Optional[dict],
    role: str,
    run_id: str,
    spawn: Callable[[], Any],
) -> Any:
    """Run ``spawn()`` and, when the flow wants windows, record what it changed.

    Returns ``spawn()``'s result unchanged. An exception from ``spawn()`` propagates and no
    window is written.
    """
    if not wants_windows(flow_config):
        return spawn()
    root = str(getattr(state, "project_root", "") or "")
    before = _take(root)
    if before is None:
        logger.info(
            "spawn_window: %s is not a git repo top (or git failed), no SPAWN_WINDOW "
            "for run %s",
            root,
            run_id,
        )
    result = spawn()
    if before is not None:
        _record(state, role, run_id, before, root)
    return result
