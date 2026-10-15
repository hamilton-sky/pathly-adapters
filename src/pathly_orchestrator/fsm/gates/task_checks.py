"""Task-check gate — ``task_checks`` (build-proof).

In ``team`` and ``team-build`` the builder claims a board task, does it and completes it itself
(``POST /comms/tasks/complete``), so the supervisor never sees per-task success; in ``goal-loop``
a builder fix round after the drain completes tasks the same way. This gate runs at every join a
completion can precede (``BUILDING->REVIEWING``, ``REVIEWING->TESTING`` and ``->DONE`` in the team
flows, ``DRAINING->DONE`` in ``goal-loop``) and executes each completed task's ``check`` block
with the same runner as ``command_gate`` (``proof/command.py``). An agent's own claim that the
checks pass does not count.

* **Which tasks:** those completed since the run-wide ``proof_base.started_at`` (goal-scoped when
  the run has a ``goal_id``, else ``(board, scope)``), minus every task whose newest ``TASK_PROOF``
  proved its current claim (``_proof_record.unproven``). So each completion is checked once: a
  task an earlier gate or the goal-loop drain proved is not run again, a task that failed is, and
  so is one that was claimed again.
* **Which text:** the text the task had when it was claimed (``claimed_text``, else ``text`` for a
  task claimed before that column existed), so editing the live text changes nothing.
* **Result:** a ``TASK_PROOF`` per task run (``floor`` is ``n/a``: ``floor_gate`` judges the
  diff). A block that cannot be parsed fails and quotes the parser's error; a task without a block
  is recorded as ``none`` and passes. The task is judged by ``proof.checks.run_task_checks``, the
  function the goal-loop drain's task proof uses too.

Fail-open: the gate skips (``GATE_SKIPPED``) when the run has no ``proof_base`` or the completed
tasks cannot be read.
"""

from __future__ import annotations

import logging
from pathlib import Path

from pathly_orchestrator.proof.checks import run_task_checks
from pathly_orchestrator.proof.command import clip_to

from . import _proof_record
from ._helpers import gate_failed, gate_skipped, project_root_of
from .command import _resolve_timeout

logger = logging.getLogger("pathly.gates.task_checks")

_GATE = "task_checks"

# The failure file lists at most this many failing tasks, each clipped to this many characters.
_MAX_TASKS = 8
_SECTION_LIMIT = 4000
_TITLE_LIMIT = 160

# A check that fails is fixed in the code; a block that cannot be read is not the builder's to fix.
_FIX_THE_CODE = (
    "**Action required:** make each failing check pass by fixing the code, then the flow "
    "advances. If the check itself is wrong, a human can correct the task text and re-freeze "
    "it (`POST /comms/tasks/floor-allow` with `refreeze: true`); an agent run cannot."
)
_ASK_A_HUMAN = (
    "**A human must fix this:** for each task above whose check block cannot be read, neither "
    "a code change nor an edit to the task text helps, because the supervisor checks the text "
    "frozen at the claim. Write `HUMAN_QUESTIONS.md` in the feedback folder next to this file, "
    "naming the task and the parse error, and stop. A human corrects the text and re-freezes "
    "it (`POST /comms/tasks/floor-allow` with `refreeze: true`)."
)


def _completed_tasks(
    since: str, goal_id: str | None, feature_scope: str | None, board: str
) -> list[dict] | None:
    """The tasks completed since ``since``; None when they cannot be read."""
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import tasks_completed_since

        return tasks_completed_since(
            get_db(), board or "feature", feature_scope or "", goal_id, since
        )
    except Exception:
        logger.warning("task_checks could not read the completed tasks", exc_info=True)
        return None


def _record(storage_path: Path, task: dict, run_id: str, result: str) -> None:
    try:
        _proof_record.record_task_proof(storage_path, task, run_id, result, "n/a")
    except Exception:
        logger.warning("task_checks could not record %s", task.get("id"), exc_info=True)


def _title(task: dict) -> str:
    for line in (task.get("claimed_text") or task.get("text") or "").splitlines():
        if line.strip():
            return clip_to(line.strip(), _TITLE_LIMIT)
    return "(no text)"


def _failure_text(failures: list[tuple[dict, str, str]]) -> str:
    """The feedback file: one section per failing task, then what the builder is to do."""
    sections = [
        "## Task %s: %s\n\n%s"
        % (task["id"], _title(task), clip_to(report, _SECTION_LIMIT))
        for task, _, report in failures[:_MAX_TASKS]
    ]
    if len(failures) > _MAX_TASKS:
        sections.append("... and %d more failing tasks" % (len(failures) - _MAX_TASKS))
    actions = []
    if any(result == "failed" for _, result, _ in failures):
        actions.append(_FIX_THE_CODE)
    if any(result == "error" for _, result, _ in failures):
        actions.append(_ASK_A_HUMAN)
    return "\n\n".join(
        [
            "Task checks: a completed task's check block failed.",
            "The supervisor ran each block itself, from the text the task had when it was "
            "claimed, so editing the task text now changes nothing. This is a MEASURED "
            "result, not a review opinion.",
            *sections,
            *actions,
            "",
        ]
    )


def check_task_checks(
    gate: dict,
    storage_path: Path,
    prev_state: str,
    next_state: str,
    *,
    goal_id: str | None = None,
    feature_scope: str | None = None,
    board: str = "feature",
    **_: object,
) -> dict | None:
    base = _proof_record.read_proof_base(storage_path)
    if base is None:
        gate_skipped(storage_path, _GATE, "no_proof_base")
        return None
    tasks = _completed_tasks(
        str(base.get("started_at") or ""), goal_id, feature_scope, board
    )
    if tasks is None:
        gate_skipped(storage_path, _GATE, "tasks_unreadable")
        return None

    run_id = "gate:%s->%s" % (prev_state, next_state)
    cwd = project_root_of(storage_path)
    timeout = _resolve_timeout({})
    failures: list[tuple[dict, str, str]] = []
    for task in _proof_record.unproven(storage_path, tasks):
        result, report = run_task_checks(task, cwd, timeout)
        _record(storage_path, task, run_id, result)
        if result in ("failed", "error"):
            failures.append((task, result, report))
    if not failures:
        return None
    return gate_failed(
        storage_path,
        gate,
        _GATE,
        prev_state,
        next_state,
        _failure_text(failures),
        extra={
            "tasks": [task["id"] for task, _, _ in failures[:_MAX_TASKS]],
            "count": len(failures),
        },
    )
