"""The run-wide proof base and the ``TASK_PROOF`` records (build-proof).

The floor and task-check gates judge the whole run, not one stage: a builder fix round runs
inside REVIEWING, TESTING, RETRO or after a goal-loop drain, and ``build_baseline`` is popped on
every transition. So ``fsm_ops.next_action`` stamps ``proof_base {tree, started_at}`` into STATE
the first time the run is in a state with an outgoing ``floor_gate`` or ``task_checks`` gate,
``fsm_ops_complete`` keeps it across every transition but the one into DONE, and a
``TASK_PROOF`` event says which task completions were already proven.

Reads state through ``eventlog.read_state`` (the DB) only, never ``STATE.json``. Never imports
``supervisor``; ``eventlog`` (and so ``db``) are imported lazily.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from pathly_orchestrator.proof import tree

logger = logging.getLogger("pathly.gates.proof_record")

# Gate types that judge the whole run since the proof base.
PROOF_GATES = frozenset({"floor_gate", "task_checks"})

CHECK_RESULTS = ("passed", "failed", "none", "error")
FLOOR_RESULTS = ("clean", "failed", "off", "n/a")


def wants_proof_base(flow_config: dict, state_name: str) -> bool:
    """True when an edge out of ``state_name`` has a ``floor_gate`` or ``task_checks`` gate.

    The edges are the ``<state>-><X>`` keys of ``gates`` and the wildcard ``-><X>`` keys, for
    every ``X`` the flow's ``transitions`` list for ``state_name``.
    """
    gates = (flow_config or {}).get("gates") or {}
    targets = ((flow_config or {}).get("transitions") or {}).get(state_name) or []
    for target in targets:
        for key in ("%s->%s" % (state_name, target), "->%s" % target):
            for gate in gates.get(key) or []:
                if isinstance(gate, dict) and gate.get("type") in PROOF_GATES:
                    return True
    return False


def stamp_proof_base(
    prior_state: dict, flow_config: dict, state_name: str, project_root: str | Path
) -> dict | None:
    """The ``proof_base`` to store now, or ``None`` when there is nothing to stamp.

    Stamped once: when ``state_name`` wants a base and ``prior_state`` has none. ``tree`` is
    ``None`` when git cannot snapshot ``project_root``; ``started_at`` is always set, because
    the task-check gate needs it without git.
    """
    if prior_state.get("proof_base") or not wants_proof_base(flow_config, state_name):
        return None
    return {
        "tree": tree.snapshot(project_root),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }


def read_proof_base(storage_path: str | Path) -> dict | None:
    """The run's stored ``proof_base``, or ``None`` when it has none or the DB cannot be read."""
    from pathly_orchestrator.eventlog import read_state

    try:
        base = (read_state(str(storage_path)) or {}).get("proof_base")
    except Exception:
        logger.warning("proof_base is unreadable for %s", storage_path, exc_info=True)
        return None
    return base if isinstance(base, dict) else None


def record_task_proof(
    storage_path: str | Path,
    task: dict,
    run_id: str,
    checks: str,
    floor: str,
    warnings: tuple[str, ...] | list[str] = (),
) -> None:
    """Append ``TASK_PROOF {task_id, claimed_at, run_id, checks, floor, warnings}``.

    ``claimed_at`` is copied from the task row, so a later claim of the same task is a
    different proof target. ``checks`` is one of ``passed``, ``failed``, ``none``, ``error``;
    ``floor`` one of ``clean``, ``failed``, ``off``, ``n/a``; anything else raises ``ValueError``.
    """
    if checks not in CHECK_RESULTS:
        raise ValueError("checks must be one of %s, not %r" % (CHECK_RESULTS, checks))
    if floor not in FLOOR_RESULTS:
        raise ValueError("floor must be one of %s, not %r" % (FLOOR_RESULTS, floor))
    from pathly_orchestrator.eventlog import append_event

    append_event(
        str(storage_path),
        {
            "type": "TASK_PROOF",
            "task_id": task["id"],
            "claimed_at": task.get("claimed_at"),
            "run_id": run_id,
            "checks": checks,
            "floor": floor,
            "warnings": list(warnings),
        },
    )


def task_proven(storage_path: str | Path, task: dict) -> bool:
    """True when the newest ``TASK_PROOF`` for ``task`` proved its current claim.

    Proved means: it carries the task's current ``claimed_at`` (a retry or a human re-open
    claims again, so an earlier record no longer counts), ``checks`` is ``passed`` or ``none``
    and ``floor`` is not ``failed``. False too when the events cannot be read: the checks then
    run again.
    """
    from pathly_orchestrator.eventlog import read_events

    try:
        events = read_events(str(storage_path))
    except Exception:
        logger.warning("TASK_PROOF is unreadable for %s", storage_path, exc_info=True)
        return False
    newest = None
    for event in events:
        if event.get("type") == "TASK_PROOF" and event.get("task_id") == task["id"]:
            newest = event
    return (
        newest is not None
        and newest.get("claimed_at") == task.get("claimed_at")
        and newest.get("checks") in ("passed", "none")
        and newest.get("floor") != "failed"
    )
