"""Scope-containment gate — ``scope_gate``.

Compares the builder's actual git footprint against the paths it declared in its scope
file. Fail-open on every read/exec problem (no baseline, no declared scope, git error):
the gate exists to catch a builder that wandered, not to wedge a run on a git hiccup.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from ._helpers import append_event, gate_failed, gate_skipped, project_root_of


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


def _git_dirty(project_root: Path, storage_path: Path) -> set[str] | None:
    """Tracked-modified ∪ untracked paths, or None when git could not be read."""
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
            ["git", "status", "--porcelain=v1"],
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


def _scope_clean(
    storage_path: Path,
    scope_file: str,
    preexisting_dirty: set[str] | None,
    flow: dict | None = None,
) -> bool:
    declared = _declared_paths(storage_path / scope_file)
    if not declared:
        gate_skipped(storage_path, "scope_gate", "no_declared_scope")
        return True

    all_dirty = _git_dirty(project_root_of(storage_path), storage_path)
    if all_dirty is None:
        return True

    builder_touched = all_dirty - (preexisting_dirty or set())

    extra_prefixes: list[str] = []
    if flow:
        extra_prefixes = flow.get("scope_gate", {}).get("exempt_prefixes", []) or []

    def _is_exempt(p: str) -> bool:
        # A feature's own storage tree is exempt from the builder scope gate: the flat home
        # (pathly/features/<name>/) and the legacy base (pathly/plans/<name>/) both count.
        if (
            p.startswith("pathly/features/")
            or p.startswith("pathly/plans/")
            or p.endswith(".tsbuildinfo")
        ):
            return True
        return any(p.startswith(prefix) for prefix in extra_prefixes)

    for path in builder_touched:
        if not _is_exempt(path) and path not in declared:
            return False

    return True


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
    **_: object,
) -> dict | None:
    scope_file = gate["scope_file"]
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
    if _scope_clean(storage_path, scope_file, preexisting, flow=flow):
        return None
    return gate_failed(
        storage_path,
        gate,
        "scope_gate",
        prev_state,
        next_state,
        f"Scope gate failed: changes outside declared scope in {scope_file}",
    )
