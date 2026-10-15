"""Prove each goal-loop task after it reports success (build-proof 05).

A DAG task used to pass on its own ``AGENT_DONE`` outcome. ``drain.drain_frontier`` now wraps the
spawn with :func:`wrap`, inside the cost tracker. For a run id of the form
``sched-<task_id>#<n>`` the wrapper snapshots the working tree before the spawn and after it
returns, and when the agent reported success it checks, in this order:

* the floor guard over the diff (``proof.floor.scan``), leaving out the paths declared in the
  ``files`` of every task whose window overlapped this one;
* the task text: a ``claimed_text`` that differs from the live ``text`` is a ``task-edit`` finding
  unless a human allowed it;
* the task's own ``check`` blocks, read from the text frozen at the claim.

It records a ``TASK_PROOF`` event (the join's ``task_checks`` gate does not run a proven task's
checks again) and, on any finding or failing check, returns the outcome with ``outcome: "failed"``
and an ``error`` holding the report. ``scheduler_loop`` then sees a failure and
``task_retry.resolve_task_failure`` retries or escalates, with the report in the next prompt.

Each attempt is judged on its own diff, so a weakening that an earlier failed attempt left in place
is not seen again by the next one; the retry prompt carries the earlier finding and the floor gate
at the goal-loop join re-checks the whole run's diff.

Fails open on anything the proof itself cannot do (no git, an unreadable task, an unexpected
error): the work is then not blocked, and the join's gates still judge it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pathly_orchestrator.proof import floor, tree
from pathly_orchestrator.proof.checks import run_task_checks
from pathly_orchestrator.proof.command import clip_to

from .scheduler import _outcome_is_failure
from .spawn_window import _storage_path

logger = logging.getLogger("pathly.task_proof")

_RUN_ID = re.compile(r"sched-(?P<task>[^#]+)#[0-9]+")

# The error text is the next attempt's failure reason (task_retry keeps up to this many characters).
_ERROR_LIMIT = 4000
_FLOOR_LIMIT = 1200
_TEXT_LIMIT = 400
_MAX_FINDINGS = 20

_LOCK = threading.Lock()
# run_id -> the window of a task whose spawn is in flight now.
_IN_FLIGHT: dict[str, "_Window"] = {}


@dataclass
class _Window:
    """A task spawn in flight: the project it edits, the paths it declared, and the paths declared
    by every task whose window overlapped it."""

    root: str
    files: set[str]
    others: set[str] = field(default_factory=set)


@dataclass
class _Verdict:
    task: dict
    storage: str
    checks: str
    floor: str
    warnings: list[str]
    error: str


def _task_id(run_id: Any) -> Optional[str]:
    found = _RUN_ID.fullmatch(run_id) if isinstance(run_id, str) else None
    return found.group("task") if found else None


def _declared(task: dict) -> set[str]:
    """The task's ``files`` as repo-relative POSIX entries; a directory covers its subtree."""
    from pathly_orchestrator.fsm.gates._scope_tasks import _task_files

    entries = set()
    for entry in _task_files(task):
        path = entry.replace("\\", "/")
        while path.startswith("./"):
            path = path[2:]
        path = path.rstrip("/")
        if path:
            entries.add(path)
    return entries


def _open_window(run_id: str, root: str, files: set[str]) -> None:
    """Register the task. Every task already in flight in the same project overlaps it."""
    window = _Window(root, set(files))
    with _LOCK:
        for other in _IN_FLIGHT.values():
            if other.root == root:
                other.others |= window.files
                window.others |= other.files
        _IN_FLIGHT[run_id] = window


def _close_window(run_id: str) -> set[str]:
    """Drop the task from the registry (idempotent); the paths its overlapping tasks declared."""
    with _LOCK:
        window = _IN_FLIGHT.pop(run_id, None)
    return set(window.others) if window is not None else set()


def _snapshot(root: str) -> Optional[str]:
    try:
        return tree.snapshot(root)
    except Exception:
        logger.warning("task_proof: snapshot of %s failed", root, exc_info=True)
        return None


def _begin(
    state: Any, run_id: str, task_id: str
) -> Optional[tuple[dict, Optional[str]]]:
    """Read the task, register its window and take the before snapshot; None = no proof."""
    root = str(getattr(state, "project_root", "") or "")
    if not root or not os.path.isdir(root):
        return None
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import get_task

        task = get_task(get_db(), task_id)
    except Exception:
        logger.warning("task_proof: could not read task %s", task_id, exc_info=True)
        return None
    if task is None or task.get("type") != "task":
        return None
    _open_window(run_id, os.path.realpath(root), _declared(task))
    return task, _snapshot(root)


def _terminal_spawn() -> Callable:
    import pathly_orchestrator.supervisor as _sup

    return _sup._run_stage_via_terminal


def _allowed(task: dict) -> frozenset[str]:
    """The floor categories a human allowed for this task (``floor_allow``, a JSON list)."""
    raw = task.get("floor_allow")
    if not raw:
        return frozenset()
    try:
        return floor.parse_allow(json.loads(raw))
    except (TypeError, ValueError):
        logger.warning("task_proof: floor_allow of %s is unreadable", task.get("id"))
        return frozenset()


def _verify_commands() -> list[str]:
    from pathly_orchestrator.fsm.gates.command import _get_setting

    found = (_get_setting("verify.%s" % key) for key in ("build", "test", "smoke"))
    return [command for command in found if command]


def _left_out(finding: str, others: set[str]) -> bool:
    """True when the finding's path is one an overlapping task declared (a directory covers
    everything under it). A finding reads ``<category>: <path>: <line>``."""
    _, _, rest = finding.partition(": ")
    return any(
        rest.startswith(entry + ": ") or rest.startswith(entry + "/")
        for entry in others
    )


def _scan(
    root: str,
    storage: str,
    before: Optional[str],
    after: Optional[str],
    allow: frozenset[str],
    others: set[str],
) -> Optional[tuple[list[str], list[str]]]:
    """``(findings, warnings)`` of the floor scan, or None when it is skipped."""
    from pathly_orchestrator.fsm.gates._proof import (
        board_home,
        floor_enabled,
        stage_writes,
    )

    if not floor_enabled() or not before or not after:
        return None
    report = floor.scan(
        root,
        before,
        after,
        allow=allow,
        protected=[board_home(storage)],
        may_change=stage_writes(storage, "builder"),
        config_commands=_verify_commands(),
    )
    warnings = list(report.warnings)
    if report.error:
        warnings.append("floor scan incomplete: %s" % report.error)
    return [f for f in report.findings if not _left_out(f, others)], warnings


def _text_findings(task: dict, allow: frozenset[str]) -> list[str]:
    frozen = task.get("claimed_text")
    if frozen is None or frozen == task.get("text") or "task-edit" in allow:
        return []
    return ["task-edit: task %s: its text was changed after the claim" % task["id"]]


def _section(heading: str, body: str, limit: int) -> str:
    return "## %s\n%s" % (heading, clip_to(body, limit - len(heading) - 4))


def _error_text(floor_lines: list[str], text_lines: list[str], report: str) -> str:
    """One short heading per failing part, then its report, in ``_ERROR_LIMIT`` characters."""
    sections: list[str] = []
    if floor_lines:
        shown = floor_lines[:_MAX_FINDINGS]
        if len(floor_lines) > len(shown):
            shown.append("... and %d more" % (len(floor_lines) - len(shown)))
        body = (
            "This attempt changed things that weaken the bar. Undo them and fix the "
            "cause instead:\n" + "\n".join(shown)
        )
        sections.append(_section("Floor guard", body, _FLOOR_LIMIT))
    if text_lines:
        body = (
            "\n".join(text_lines)
            + "\nPut the task text back: the checks use the text frozen at the claim."
        )
        sections.append(_section("Task text", body, _TEXT_LIMIT))
    if report:
        used = sum(len(s) for s in sections) + 2 * len(sections)
        sections.append(_section("Checks", report, max(_ERROR_LIMIT - used, 200)))
    return "\n\n".join(sections)


def _judge(
    state: Any,
    task: dict,
    before: Optional[str],
    after: Optional[str],
    others: set[str],
) -> _Verdict:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.task_proof import get_task
    from pathly_orchestrator.fsm.gates.command import _resolve_timeout

    root = str(state.project_root)
    storage = _storage_path(state)
    task = get_task(get_db(), task["id"]) or task
    allow = _allowed(task)
    scanned = _scan(root, storage, before, after, allow, others)
    floor_lines, warnings = scanned if scanned is not None else ([], [])
    text_lines = _text_findings(task, allow)
    checks, report = run_task_checks(task, root, _resolve_timeout({}))
    if floor_lines or text_lines:
        floor_result = "failed"
    else:
        floor_result = "off" if scanned is None else "clean"
    failing = checks in ("failed", "error")
    error = ""
    if floor_lines or text_lines or failing:
        error = _error_text(floor_lines, text_lines, report if failing else "")
    return _Verdict(task, storage, checks, floor_result, warnings, error)


def _prove(
    state: Any,
    run_id: str,
    task: dict,
    before: Optional[str],
    after: Optional[str],
    others: set[str],
    outcome: Any,
) -> Any:
    """``outcome`` unchanged when the task is proven, else a failed copy carrying the report."""
    from pathly_orchestrator.fsm.gates._proof_record import record_task_proof

    try:
        verdict = _judge(state, task, before, after, others)
    except Exception:
        logger.warning(
            "task_proof: %s could not be proven; not blocking it", run_id, exc_info=True
        )
        return outcome
    try:
        record_task_proof(
            verdict.storage,
            verdict.task,
            run_id,
            verdict.checks,
            verdict.floor,
            verdict.warnings,
        )
    except Exception:
        logger.warning("task_proof: could not record %s", run_id, exc_info=True)
    if not verdict.error:
        return outcome
    logger.info("task_proof: %s failed its proof", run_id)
    failed = dict(outcome) if isinstance(outcome, dict) else {}
    failed["outcome"] = "failed"
    failed["error"] = verdict.error
    return failed


def wrap(spawn_fn: Optional[Callable]) -> Callable:
    """A spawn function with ``scheduler._worker``'s signature that proves a DAG task.

    ``spawn_fn=None`` means the terminal spawn, looked up on ``pathly_orchestrator.supervisor``
    each time the wrapper is called (so a test that patches it still works). A run id that is not
    ``sched-<task_id>#<n>`` passes straight through.
    """

    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        spawn = spawn_fn if spawn_fn is not None else _terminal_spawn()
        task_id = _task_id(run_id)
        begun = _begin(state, run_id, task_id) if task_id else None
        if begun is None:
            return spawn(state, instructions, adapter, model, run_id, broadcast_fn)
        task, before = begun
        try:
            outcome = spawn(state, instructions, adapter, model, run_id, broadcast_fn)
            if _outcome_is_failure(outcome):
                return outcome
            after = _snapshot(str(state.project_root))
            others = _close_window(run_id)
        finally:
            _close_window(run_id)
        return _prove(state, run_id, task, before, after, others, outcome)

    return _spawn
