"""Transition gates — one module per gate type, dispatched by :func:`run_gates`.

A gate answers ONE question: may the FSM leave ``prev_state`` for ``next_state``? Each
check returns ``None`` to allow the transition, or a ``{"gate_failed", "feedback_file"}``
dict to block it and route feedback.

| Gate | Module | Proves |
|---|---|---|
| ``require_artifact`` | ``artifact`` | an agent wrote a file |
| ``verify_gate`` | ``artifact`` | an agent wrote a pass marker |
| ``require_tasks_done`` | ``tasks`` | the board DAG has no unfinished task |
| ``scope_gate`` | ``scope`` | the builder stayed inside its declared footprint |
| ``command_gate`` | ``command`` | **the project's own verify command exits 0** |
| ``reviewer_unchanged`` | ``reviewer`` | a reviewer spawn changed no file and made no commit |
| ``floor_gate`` | ``floor`` | **the run's diff weakens no test, check, config or plan** |
| ``task_checks`` | ``task_checks`` | **each completed task's ``check`` block exits as it says** |

The first four read state that agents produced; ``command_gate`` and ``task_checks`` execute
something and read a real exit code. Reach for them whenever a claim can be measured.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ._helpers import (
    append_event,
    gate_failed,
    gate_skipped,
    project_root_of,
    _write_gate_feedback,
)
from .artifact import _verify_passed, check_require_artifact, check_verify_gate
from .command import check_command_gate
from .floor import check_floor_gate
from .reviewer import check_reviewer_unchanged
from .scope import _scope_clean, check_scope_gate
from .task_checks import check_task_checks
from .tasks import check_require_tasks_done

# Every check takes (gate, storage_path, prev_state, next_state) plus the shared keyword
# context below, and swallows the kwargs it does not use — so one dispatch call fits all.
_GateCheck = Callable[..., "dict | None"]

_CHECKS: dict[str, _GateCheck] = {
    "require_artifact": check_require_artifact,
    "verify_gate": check_verify_gate,
    "require_tasks_done": check_require_tasks_done,
    "scope_gate": check_scope_gate,
    "command_gate": check_command_gate,
    "reviewer_unchanged": check_reviewer_unchanged,
    "floor_gate": check_floor_gate,
    "task_checks": check_task_checks,
}

__all__ = [
    "run_gates",
    "append_event",
    "gate_failed",
    "gate_skipped",
    "project_root_of",
    "_write_gate_feedback",
    "_verify_passed",
    "_scope_clean",
]


def run_gates(
    flow: dict,
    prev_state: str,
    next_state: str,
    storage_path: Path,
    topic: str,
    conv: int,
    goal_id: str | None = None,
    feature_scope: str | None = None,
    board: str = "feature",
) -> dict | None:
    """Run every gate declared for this transition. First failure wins and blocks."""
    gates = flow.get("gates", {})
    applicable = gates.get(f"{prev_state}->{next_state}", []) + gates.get(
        f"->{next_state}", []
    )

    for gate in applicable:
        gtype = gate["type"]
        check = _CHECKS.get(gtype)
        if check is None:
            raise RuntimeError(f"Unknown gate type: {gtype!r}")
        failure = check(
            gate,
            storage_path,
            prev_state,
            next_state,
            flow=flow,
            goal_id=goal_id,
            feature_scope=feature_scope,
            board=board,
        )
        if failure is not None:
            return failure
    return None
