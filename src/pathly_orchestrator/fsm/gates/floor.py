"""Floor-guard gate — ``floor_gate`` (build-proof).

A build can get green by weakening the bar: skip a test, silence a linter, edit the config or
the plan. ``command_gate`` then passes on the weakened project, so this gate reads the diff
itself. It compares the working tree now with the run-wide ``proof_base`` that ``next_action``
stamped on the first state with an outgoing ``floor_gate`` (kept until DONE), so a builder fix
round that ran inside REVIEWING, TESTING, RETRO or after a goal-loop drain is judged at the next
transition, whichever stage it ran in. ``proof.floor.scan`` does the judging.

* The allow list is the union of the ``floor_allow`` lists a human set on the tasks claimed since
  the base (``POST /comms/tasks/floor-allow``); an agent cannot set one.
* A claimed task whose text changed since the claim is a ``task-edit`` finding unless that task
  allows ``task-edit``.
* A file under the run's board home is a ``plan-edit`` unless the builder stage may write it
  (``_proof.stage_writes``) or a ``SPAWN_WINDOW`` of a role that may write it explains it, so a
  planner's routed edit or the reviewer's ``REVIEW.md`` is not blamed on the builder. A run with
  no window at all (an interactive run) cannot attribute a plan file, so there a path some role
  may write is excused, with a note in ``FLOOR_CHECKED``; a path no role may write still counts.

``FLOOR_CHECKED {warnings}`` is appended whenever a scan ran (the reviewer's packet reads it).
Fail-open: the gate skips (``GATE_SKIPPED``) when the guard is off, the run has no base, no
snapshot (not a git repo) or no readable tasks, and when an unexpected error stops the scan.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

from pathly_orchestrator.proof import floor as proof_floor
from pathly_orchestrator.proof import tree

from . import _proof, _proof_record
from ._helpers import append_event, gate_failed, gate_skipped, project_root_of
from .command import _get_setting

logger = logging.getLogger("pathly.gates.floor")

_GATE = "floor_gate"

# The failure text lists at most this many findings, then a count of the rest.
_MAX_LISTED = 30


def _claimed_tasks(
    since: str, goal_id: str | None, feature_scope: str | None, board: str
) -> list[dict] | None:
    """The tasks claimed since ``since`` (goal-scoped, else ``(board, scope)``); None if unreadable."""
    if not (goal_id or feature_scope):
        return []
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import tasks_claimed_since

        return tasks_claimed_since(
            get_db(), board or "feature", feature_scope or "", goal_id, since
        )
    except Exception:
        logger.warning("floor_gate could not read the claimed tasks", exc_info=True)
        return None


def _allowed(task: dict) -> frozenset[str]:
    """The floor categories a human allowed for this task (``floor_allow``, a JSON list)."""
    raw = task.get("floor_allow")
    if not raw:
        return frozenset()
    try:
        return proof_floor.parse_allow(json.loads(raw))
    except (TypeError, ValueError):
        logger.warning("floor_allow of task %s is unreadable", task.get("id"))
        return frozenset()


def _task_edits(tasks: list[dict]) -> list[str]:
    """A ``task-edit`` finding per claimed task whose text changed since the claim."""
    found = []
    for task in tasks:
        frozen = task.get("claimed_text")
        if frozen is None or frozen == task.get("text"):
            continue
        if "task-edit" not in _allowed(task):
            found.append(
                "task-edit: task %s: its text was changed after the claim" % task["id"]
            )
    return found


def _verify_commands() -> list[str]:
    found = (
        _get_setting("verify.%s" % key) for key in ("build", "test", "lint", "smoke")
    )
    return [command for command in found if command]


def _may_change(
    root: Path, storage_path: Path, started_at: str, now_tree: str, notes: list[str]
) -> Callable[[str], bool]:
    """A predicate for the scan: may this plan path have changed without the builder's doing?

    True for what the builder stage may write, else for a path a ``SPAWN_WINDOW`` since the base
    explains. The windows are read once, on the first path that needs them. When they cannot be
    read, or were read and there are none (an interactive run records none), a path some role may
    write is excused (and ``notes`` says which), so a DB hiccup or a run without windows does not
    blame the builder for the reviewer's ``REVIEW.md``; a path no role may write still counts.
    With at least one window, only an explaining window excuses a path.
    """
    builder = _proof.stage_writes(storage_path, "builder")
    any_role = _proof.any_role_writes(storage_path)
    loaded: list[list[dict] | None] = []

    def windows() -> list[dict] | None:
        if not loaded:
            try:
                loaded.append(_proof.windows_since(storage_path, started_at))
            except Exception:
                logger.warning("floor_gate could not read the windows", exc_info=True)
                notes.append(
                    "spawn windows unreadable: plan files a role may write were not judged"
                )
                loaded.append(None)
            else:
                if not loaded[0]:
                    notes.append(
                        "the run recorded no spawn windows: plan files a role may write "
                        "were not judged"
                    )
        return loaded[0]

    def may_change(path: str) -> bool:
        if builder(path):
            return True
        found = windows()
        if not found:
            return any_role(path)
        return _proof.explained(root, path, now_tree, found, storage_path)

    return may_change


def _failure_text(findings: list[str]) -> str:
    listed = ["- " + line for line in findings[:_MAX_LISTED]]
    if len(findings) > _MAX_LISTED:
        listed.append("- ... and %d more" % (len(findings) - _MAX_LISTED))
    return "\n".join(
        [
            "Floor guard: the diff weakens the bar instead of meeting it.",
            "",
            "Everything this run has changed since it began was scanned. This is a "
            "MEASURED result, not a review opinion. Findings (`<category>: <path>: <line>`):",
            "",
            *listed,
            "",
            "A human can allow a category for a claimed task with `POST "
            '/comms/tasks/floor-allow` (`{"message_id": "<task id>", "allow": '
            '["skip"]}`), or turn the guard off with the `floor.enabled` app setting '
            "(`PUT /db/settings/floor.enabled`, value `false`); the setting is the only "
            "way out when no task was claimed. An agent run cannot do either.",
            "",
            "**Action required:** undo each change listed above and fix the cause "
            "instead: make the code meet the test, the check or the plan as it stood, "
            "then the flow advances.",
            "",
        ]
    )


def _scan(
    storage_path: Path, base: dict, tasks: list[dict], notes: list[str]
) -> proof_floor.FloorReport | None:
    """The floor scan of the working tree against the base; None when there is no snapshot."""
    root = project_root_of(storage_path)
    now = tree.snapshot(root)
    if not now:
        gate_skipped(storage_path, _GATE, "snapshot_failed")
        return None
    allow = frozenset(category for task in tasks for category in _allowed(task))
    return proof_floor.scan(
        root,
        base["tree"],
        now,
        allow=allow,
        protected=[_proof.board_home(storage_path)],
        may_change=_may_change(
            root, storage_path, str(base.get("started_at") or ""), now, notes
        ),
        config_commands=_verify_commands(),
    )


def check_floor_gate(
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
    if not _proof.floor_enabled():
        gate_skipped(storage_path, _GATE, "floor_disabled")
        return None
    base = _proof_record.read_proof_base(storage_path)
    if base is None:
        gate_skipped(storage_path, _GATE, "no_proof_base")
        return None
    if not base.get("tree"):
        gate_skipped(storage_path, _GATE, "no_snapshot")
        return None
    tasks = _claimed_tasks(
        str(base.get("started_at") or ""), goal_id, feature_scope, board
    )
    if tasks is None:
        gate_skipped(storage_path, _GATE, "tasks_unreadable")
        return None

    notes: list[str] = []
    try:
        report = _scan(storage_path, base, tasks, notes)
    except Exception:
        logger.warning("floor_gate could not scan the diff", exc_info=True)
        gate_skipped(storage_path, _GATE, "scan_failed")
        return None
    if report is None:
        return None

    findings = report.findings + _task_edits(tasks)
    warnings = report.warnings + notes
    if report.error:
        warnings.append("floor scan incomplete: %s" % report.error)
    append_event(storage_path, {"type": "FLOOR_CHECKED", "warnings": warnings})

    if findings:
        return gate_failed(
            storage_path,
            gate,
            _GATE,
            prev_state,
            next_state,
            _failure_text(findings),
            extra={"findings": findings[:_MAX_LISTED], "count": len(findings)},
        )
    if report.error:
        gate_skipped(storage_path, _GATE, "scan_incomplete")
    return None
