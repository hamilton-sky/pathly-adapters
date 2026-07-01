"""Shared feature-discovery for the pathly-* CLI shortcuts (status / ff / back / log).

Scans the legacy nested roots (pathly/plans, pathly/debugs, pathly/explorations) AND the
new top-level feature root (pathly/<feature>/), so a feature created at the new root — the
one ``fsm_ops._resolve_storage_path`` now prefers — is visible to the CLI. Reserved
container dirs under pathly/ are skipped; results de-duplicate by resolved path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

# (relative root, flow label) for the legacy nested layout.
SCAN_ROOTS = [
    ("pathly/plans", "team"),
    ("pathly/debugs", "debug"),
    ("pathly/explorations", "explore"),
]

# Direct children of pathly/ that are containers, not features — never a feature dir.
_RESERVED = {"plans", "debugs", "explorations", "goals", ".archive", "pipeline-walkthrough"}


def iter_state_files(cwd: Path) -> Iterator[tuple[Path, str]]:
    """Yield ``(state_file, flow)`` for every feature across the legacy roots and the new
    top-level ``pathly/<feature>/`` root. Skips ``.archive`` and reserved container dirs;
    de-duplicates by resolved path so a feature is never counted twice."""
    seen: set[str] = set()
    pairs: list[tuple[Path, str]] = []

    for root_rel, flow in SCAN_ROOTS:
        root = cwd / root_rel
        if root.is_dir():
            for sf in root.glob("*/STATE.json"):
                pairs.append((sf, flow))

    pathly = cwd / "pathly"
    if pathly.is_dir():
        for sf in pathly.glob("*/STATE.json"):
            if sf.parent.name not in _RESERVED:
                pairs.append((sf, "team"))

    for sf, flow in pairs:
        if ".archive" in sf.parts:
            continue
        key = str(sf.resolve())
        if key in seen:
            continue
        seen.add(key)
        yield sf, flow


def find_most_recent_state(cwd: Path) -> tuple[Path, str, str] | None:
    """``(storage_path, topic, flow)`` for the most-recently-modified feature, or None."""
    best_mtime = -1.0
    best: tuple[Path, str, str] | None = None
    for state_file, flow in iter_state_files(cwd):
        try:
            mtime = state_file.stat().st_mtime
        except OSError:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best = (state_file.parent, state_file.parent.name, flow)
    return best


def find_topic_dir(cwd: Path, topic: str) -> tuple[Path, str] | None:
    """``(storage_path, flow)`` for a named topic — the new top-level root
    (``pathly/<topic>/``) is preferred, then the legacy nested roots."""
    new_root = cwd / "pathly" / topic
    if (new_root / "STATE.json").exists():
        return new_root, "team"
    for root_rel, flow in SCAN_ROOTS:
        candidate = cwd / root_rel / topic
        if (candidate / "STATE.json").exists():
            return candidate, flow
    return None
