"""Scope-containment gate — ``scope_gate``.

Compares the builder's actual git footprint against its declared scope: the backtick paths in
the gate's ``scope_file`` (optional) plus the ``files`` of the board tasks claimed since
``build_baseline.started_at``. A declared directory covers everything under it. Exempt: what
the builder stage may write (``_proof.stage_writes``: its feedback files, ``VERIFY.md``, the
server's exports, ``*.tsbuildinfo``), the flow's ``scope_gate.exempt_prefixes``, and a path a
``SPAWN_WINDOW`` explains (a planner routed a feedback file edits the plan). The rest of
``pathly/`` is not exempt, so a builder that rewrites its own plan fails.

Fail-open on every read/exec problem (no baseline, no declared scope, git error, unreadable
tasks or windows): the gate exists to catch a builder that wandered, not to wedge a run on a
git hiccup.
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Iterable
from pathlib import Path

from pathly_orchestrator.proof import tree

from . import _proof
from ._helpers import append_event, gate_failed, gate_skipped, project_root_of

logger = logging.getLogger("pathly.gates.scope")

# The failure text names at most this many paths, then a count of the rest.
_MAX_NAMED = 20


def _declared_paths(scope_path: Path) -> set[str]:
    """Backtick-quoted paths named in the scope file."""
    import re as _re

    declared: set[str] = set()
    if not scope_path.exists():
        return declared
    try:
        text = scope_path.read_text(encoding="utf-8")
    except OSError:
        return declared
    for line in text.splitlines():
        for match in _re.finditer(r"`([^`\r\n]+)`", line):
            candidate = match.group(1).strip()
            if candidate:
                declared.add(candidate)
    return declared


def _task_files(task: dict) -> set[str]:
    """A task row's declared ``files`` (a JSON list), or nothing when absent or malformed."""
    try:
        parsed = json.loads(task.get("files") or "[]")
    except (TypeError, ValueError):
        return set()
    if not isinstance(parsed, list):
        return set()
    return {str(f).strip() for f in parsed if str(f).strip()}


def _claimed_files(
    since: str | None, goal_id: str | None, feature_scope: str | None, board: str
) -> set[str] | None:
    """The ``files`` of the tasks claimed since ``since``; None when the board cannot be read."""
    if not since or not (goal_id or feature_scope):
        return set()
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.task_proof import tasks_claimed_since

        tasks = tasks_claimed_since(
            get_db(), board or "feature", feature_scope or "", goal_id, since
        )
    except Exception:
        logger.warning("scope_gate could not read the claimed tasks", exc_info=True)
        return None
    files: set[str] = set()
    for task in tasks:
        files |= _task_files(task)
    return files


def _covered(path: str, entries: Iterable[str]) -> bool:
    """True when an entry names ``path`` or a directory above it (trailing ``/`` or not)."""
    for entry in entries:
        name = entry.strip().replace("\\", "/").rstrip("/")
        if name and (path == name or path.startswith(name + "/")):
            return True
    return False


def _git_dirty(project_root: Path, storage_path: Path) -> set[str] | None:
    """Tracked-modified ∪ untracked paths, or None when git could not be read.

    Untracked files are listed one by one (``--untracked-files=all``): git otherwise names a
    new folder as one ``dir/`` line, which no declared file inside it would match.
    """
    try:
        diff_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        gate_skipped(storage_path, "scope_gate", "git_diff_failed")
        return None

    if diff_result.returncode != 0:
        gate_skipped(storage_path, "scope_gate", "git_diff_failed")
        return None

    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
        untracked = (
            {
                line[3:].strip()
                for line in status_result.stdout.splitlines()
                if line.startswith("??")
            }
            if status_result.returncode == 0
            else set()
        )
    except Exception:
        untracked = set()

    return {p for p in diff_result.stdout.splitlines() if p.strip()} | untracked


def _unexplained(
    storage_path: Path, project_root: Path, paths: list[str], since: str | None
) -> list[str] | None:
    """``paths`` without those a ``SPAWN_WINDOW`` since ``since`` explains; None to skip.

    Only a path some window's role may write can be explained, so the snapshot of the working
    tree is taken only when such a path exists.
    """
    try:
        windows = _proof.windows_since(storage_path, since)
    except Exception:
        logger.warning("scope_gate could not read the spawn windows", exc_info=True)
        gate_skipped(storage_path, "scope_gate", "spawn_windows_unreadable")
        return None
    writers = [
        _proof.stage_writes(storage_path, role)
        for role in {window.get("role") for window in windows}
    ]
    needy = {p for p in paths if any(may_write(p) for may_write in writers)}
    if not needy:
        return paths
    now = tree.snapshot(project_root)
    if now is None:
        gate_skipped(storage_path, "scope_gate", "snapshot_failed")
        return None
    return [
        p
        for p in paths
        if p not in needy
        or not _proof.explained(project_root, p, now, windows, storage_path)
    ]


def _out_of_scope(
    storage_path: Path,
    declared: set[str],
    preexisting_dirty: set[str] | None,
    flow: dict | None = None,
    since: str | None = None,
    scope_file: str | None = None,
) -> list[str] | None:
    """Changed paths outside the declared scope, sorted; None when the gate must skip.

    A path dirty before the build started (``preexisting_dirty``, where a ``dir/`` entry covers
    the files under it) is not the builder's. The scope file never covers its own edit, so a
    builder cannot widen its scope by rewriting it.
    """
    project_root = project_root_of(storage_path)
    all_dirty = _git_dirty(project_root, storage_path)
    if all_dirty is None:
        return None

    extra_prefixes: list[str] = []
    if flow:
        extra_prefixes = (flow.get("scope_gate") or {}).get("exempt_prefixes") or []
    builder_may_write = _proof.stage_writes(storage_path, "builder")
    storage_rel = _proof._storage_rel(storage_path)
    own_scope_file = (
        "/".join(p for p in (storage_rel, scope_file) if p) if scope_file else None
    )

    def _in_scope(path: str) -> bool:
        if _covered(path, preexisting_dirty or ()) or builder_may_write(path):
            return True
        if any(path.startswith(prefix) for prefix in extra_prefixes):
            return True
        return path != own_scope_file and _covered(path, declared)

    outside = sorted(p for p in all_dirty if not _in_scope(p))
    if not outside:
        return []
    return _unexplained(storage_path, project_root, outside, since)


def _scope_clean(
    storage_path: Path,
    scope_file: str,
    preexisting_dirty: set[str] | None,
    flow: dict | None = None,
) -> bool:
    """The gate's rule as a yes/no, with ``scope_file``'s paths as the whole declared scope.

    Skips (True) when the file declares nothing or a read fails.
    """
    declared = _declared_paths(storage_path / scope_file)
    if not declared:
        gate_skipped(storage_path, "scope_gate", "no_declared_scope")
        return True
    outside = _out_of_scope(
        storage_path, declared, preexisting_dirty, flow=flow, scope_file=scope_file
    )
    return not outside


def _failure_text(
    outside: list[str],
    scope_file: str | None,
    named_in_file: bool,
    tasks_declared: bool,
) -> str:
    sources = []
    if named_in_file:
        sources.append(f"the paths named in `{scope_file}`")
    if tasks_declared:
        sources.append("the `files` of the tasks claimed since this build started")
    listed = [f"- {path}" for path in outside[:_MAX_NAMED]]
    if len(outside) > _MAX_NAMED:
        listed.append(f"- ... and {len(outside) - _MAX_NAMED} more")
    return "\n".join(
        [
            f"Scope gate failed: {len(outside)} changed path(s) are outside the declared "
            "scope.",
            "",
            "Declared scope: " + " and ".join(sources) + ". Your feedback files and "
            "`VERIFY.md` are always allowed; plan files are not.",
            "",
            "Outside it:",
            *listed,
            "",
            "Undo these changes. If the work really needs one of them, do not edit the plan "
            "or a task yourself: write feedback/IMPL_QUESTIONS.md so the planner can widen "
            "the scope.",
            "",
        ]
    )


def _read_build_baseline(storage_path: Path) -> dict | None:
    try:
        from pathly_orchestrator.eventlog import read_state as _read_state_db

        _state_doc = _read_state_db(str(storage_path))
        if _state_doc:
            return _state_doc.get("build_baseline")
    except Exception:
        pass
    # pathly:allow-mirror-read: DB-first build_baseline fallback — disk snapshot only when DB has no row
    state_file = storage_path / "STATE.json"
    if state_file.exists():
        try:
            state_doc = json.loads(state_file.read_text(encoding="utf-8"))
            return state_doc.get("build_baseline")
        except (json.JSONDecodeError, OSError):
            pass
    return None


def check_scope_gate(
    gate: dict,
    storage_path: Path,
    prev_state: str,
    next_state: str,
    flow: dict | None = None,
    goal_id: str | None = None,
    feature_scope: str | None = None,
    board: str = "feature",
    **_: object,
) -> dict | None:
    scope_file = gate.get("scope_file")
    build_baseline = _read_build_baseline(storage_path)
    if build_baseline is None:
        gate_skipped(storage_path, "scope_gate", "no_build_baseline")
        return None
    if (
        build_baseline.get("truncated")
        or len(build_baseline.get("preexisting_dirty", [])) > 500
    ):
        append_event(
            storage_path,
            {
                "type": "GATE_DEGRADED",
                "gate": "scope_gate",
                "reason": "preexisting_dirty_truncated",
            },
        )
        return None
    preexisting = set(build_baseline.get("preexisting_dirty", []))
    since = build_baseline.get("started_at")

    named = _declared_paths(storage_path / scope_file) if scope_file else set()
    task_files = _claimed_files(since, goal_id, feature_scope, board)
    if task_files is None:
        gate_skipped(storage_path, "scope_gate", "tasks_unreadable")
        return None
    declared = named | task_files
    if not declared:
        gate_skipped(storage_path, "scope_gate", "no_declared_scope")
        return None

    outside = _out_of_scope(
        storage_path, declared, preexisting, flow, since=since, scope_file=scope_file
    )
    if not outside:
        return None
    return gate_failed(
        storage_path,
        gate,
        "scope_gate",
        prev_state,
        next_state,
        _failure_text(outside, scope_file, bool(named), bool(task_files)),
    )
