"""Is this DAG's lane partition safe to run in parallel? (fsm-fan-out C.5)

``scheduler_loop``'s only concurrency-safety rule is **at most one worker per lane**, and
``LaneIsolation``'s docstring states the assumption that makes that a safety rule rather
than a scheduling detail: *"disjoint file sets per lane"*. Nothing enforced that assumption,
and nothing even recorded the inputs to it — ``lane`` had no write path at all and ``files``
could not be set through ``/comms/post``, so every task arrived with both NULL. The
scheduler's ``lane or task_id`` fallback then put every task in its own lane, which makes
one-worker-per-lane vacuously true and the rule worth nothing.

C.5 gave both columns a write path. This module is the other half: it *checks* the
assumption instead of trusting it, so turning parallelism on (Phase D) can be gated on
evidence rather than on a planner having been careful.

Two ways a partition is unsafe, and they are different failures:

- **undeclared** — a task declares no ``files``. Its footprint is unknown, so no claim about
  disjointness can be made about it at all. This is not "probably fine": it is the case
  ``file_claims`` models as the WILDCARD, overlapping everything.
- **conflicts** — two tasks in DIFFERENT lanes declare OVERLAPPING files. The scheduler is
  free to run them at once, and they would write the same paths from two agents.

Read-only and never raises: a caller can audit a board mid-run without affecting it.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from . import file_claims

logger = logging.getLogger("pathly.lane_partition")


def _declared_files(row: Any) -> list[str]:
    """The task's declared footprint, or [] when absent/malformed."""
    try:
        raw = row["files"]
    except (KeyError, IndexError, TypeError):
        return []
    try:
        parsed = json.loads(raw or "[]")
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(f).strip() for f in parsed if str(f).strip()]


def audit_lane_partition(
    conn, board: str, scope: str, goal_id: Optional[str] = None
) -> dict:
    """Audit the ready frontier's lane partition. Returns a report; never raises.

    ``safe`` is the predicate a parallel isolation may be gated on: every ready task
    declares a footprint AND no two tasks in different lanes overlap. An EMPTY frontier is
    safe (nothing to collide), which keeps the gate from blocking a drained board.

    Deliberately audits the READY frontier — the same ``get_ready_tasks`` set the scheduler
    would actually schedule — rather than every task on the board. A task still blocked
    behind ``depends_on`` cannot run concurrently with anything, so counting it would
    report conflicts that the DAG already prevents.
    """
    report: dict = {
        "tasks": 0,
        "undeclared": [],
        "conflicts": [],
        "safe": True,
        "reason": "",
    }
    try:
        from pathly_orchestrator.db.queries.comms import get_ready_tasks

        ready = get_ready_tasks(conn, boards=[board], scopes=[scope], goal_id=goal_id)
    except Exception:
        logger.debug("lane_partition: could not read the frontier", exc_info=True)
        report["safe"] = False
        report["reason"] = "frontier could not be read"
        return report

    report["tasks"] = len(ready)
    declared: list[tuple[str, str, list[str]]] = []
    for task in ready:
        task_id = task["id"]
        # The scheduler's OWN fallback (scheduler.py: `lane or task_id`) — audit the lane
        # the scheduler would actually use, not the raw column, or a NULL lane would look
        # like a shared lane here and like a private one there.
        lane = task.get("lane") or task_id
        files = _declared_files(task)
        if not files:
            report["undeclared"].append(task_id)
            continue
        declared.append((task_id, lane, files))

    for i, (id_a, lane_a, files_a) in enumerate(declared):
        for id_b, lane_b, files_b in declared[i + 1 :]:
            if lane_a == lane_b:
                continue  # same lane: the scheduler already serialises these
            if file_claims.overlaps(files_a, files_b):
                report["conflicts"].append(
                    {
                        "a": id_a,
                        "b": id_b,
                        "lanes": [lane_a, lane_b],
                        "files": sorted(set(files_a) & set(files_b)) or ["(prefix)"],
                    }
                )

    if report["undeclared"]:
        report["safe"] = False
        report["reason"] = (
            f"{len(report['undeclared'])} of {report['tasks']} ready task(s) declare no "
            f"files — an undeclared footprint overlaps everything"
        )
    elif report["conflicts"]:
        report["safe"] = False
        report["reason"] = (
            f"{len(report['conflicts'])} cross-lane file overlap(s) — tasks in different "
            f"lanes would write the same paths concurrently"
        )
    return report
