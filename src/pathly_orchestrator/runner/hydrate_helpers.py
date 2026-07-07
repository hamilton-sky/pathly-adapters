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


def safe_artifact_path(
    scope: str, artifact: str, project_root: str | None
) -> str | None:
    """Resolve a board artifact ref to an absolute path under *project_root*, or None.

    Supersedes ``safe_plan_path`` for hydration. context_refs store artifact paths in
    two shapes, and the storage-restructure moved feature homes out of ``pathly/plans/``:

      • repo-relative path (``pathly/features/<f>/PROPOSAL.md``) → resolved under
        ``project_root`` directly — this is how context_refs are written today.
      • bare basename (``PROPOSAL.md``) → tried under ``pathly/features/<scope>/``
        first, then legacy ``pathly/plans/<scope>/``.

    Traversal guard (unchanged intent): rejects absolute paths and ``..`` segments; the
    resolved realpath must stay under ``project_root``. Returns None on any violation.
    """
    if not project_root or not artifact or not artifact.strip():
        return None
    root_real = os.path.realpath(project_root)

    def _contained(*parts: str) -> str | None:
        candidate = os.path.realpath(os.path.join(project_root, *parts))
        root_nc = os.path.normcase(root_real)
        cand_nc = os.path.normcase(candidate)
        if cand_nc == root_nc or cand_nc.startswith(root_nc + os.sep):
            return candidate
        return None

    art_norm = artifact.replace("\\", "/")
    if os.path.isabs(art_norm) or any(seg == ".." for seg in art_norm.split("/")):
        return None

    # Full repo-relative ref — accepted ONLY within a known pathly/ subtree
    # (context_refs point at pathly/features|plans|goals|project/...). Any other
    # separator-bearing artifact is rejected so the public /section route cannot be
    # used to read arbitrary .md files under the repo root.
    if "/" in art_norm:
        _known_roots = (
            "pathly/features/",
            "pathly/plans/",
            "pathly/goals/",
            "pathly/project/",
        )
        if not any(art_norm.startswith(root) for root in _known_roots):
            return None
        return _contained(art_norm)

    # Bare basename: the scope must itself be a single safe segment.
    scope_norm = (scope or "").replace("\\", "/")
    if (
        not scope_norm
        or os.path.isabs(scope_norm)
        or "/" in scope_norm
        or any(seg == ".." for seg in scope_norm.split("/"))
    ):
        return None
    for base in ("features", "plans"):
        cand = _contained("pathly", base, scope, artifact)
        if cand and os.path.exists(cand):
            return cand
    # Neither layout has the file — return the current-layout candidate so the caller
    # reports a consistent artifact_not_found (404) rather than a resolution None.
    return _contained("pathly", "features", scope, artifact)


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
