"""Pure path helpers for the hydration engine (no DB, no inference)."""

from __future__ import annotations

import os


def _is_md(path: str) -> bool:
    """Return True when path has a .md extension (case-insensitive)."""
    return path.lower().endswith(".md")


def safe_plan_path(scope: str, artifact: str, project_root: str | None) -> str | None:
    """Resolve <project_root>/pathly/plans/<scope>/<artifact> only within the plan tree.

    Returns None on any traversal attempt. Rejects scope/artifact containing path
    separators, '..' segments, or absolute paths. Uses realpath + normcase containment.
    """
    if not project_root:
        return None
    for part, _ in ((scope, "scope"), (artifact, "artifact")):
        if not part or not part.strip():
            return None
        if os.path.isabs(part):
            return None
        normalized = part.replace("\\", "/")
        if "/" in normalized or os.sep in normalized:
            return None
        if any(seg == ".." for seg in normalized.split("/")):
            return None
    root = os.path.realpath(os.path.join(project_root, "pathly", "plans", scope))
    candidate = os.path.realpath(os.path.join(root, artifact))
    root_nc = os.path.normcase(root)
    candidate_nc = os.path.normcase(candidate)
    if candidate_nc == root_nc or candidate_nc.startswith(root_nc + os.sep):
        return candidate
    return None


def _resolve_plan_root(scope: str, project_root: str | None = None) -> str:
    """Return the absolute path to pathly/plans/<scope>/. Falls back to cwd when absent."""
    base = project_root or os.getcwd()
    return os.path.normpath(os.path.join(base, "pathly", "plans", scope))


def _read_file_text(path: str) -> str | None:
    """Return file text, or None when unreadable."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None
