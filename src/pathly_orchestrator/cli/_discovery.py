"""Shared feature-discovery for the pathly-* CLI shortcuts (status / ff / back / log).

Covers three storage layouts so a feature is found wherever it lives:
  - feature-centric (new):  pathly/features/<name>/plans/STATE.json
  - type-nested (legacy):   pathly/plans|debugs|explorations/<name>/STATE.json
  - flat (legacy):          pathly/<name>/STATE.json

Reserved container dirs under pathly/ are skipped; results de-dupe by resolved path.
Each result carries its own ``topic`` (the FEATURE name) because it is NOT always
``state_file.parent.name`` — for the feature-centric layout the name is the grandparent
(``pathly/features/<name>/plans/``), not the immediate parent (``plans``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

# (relative root, flow label) for the legacy type-nested layout.
SCAN_ROOTS = [
    ("pathly/plans", "team"),
    ("pathly/debugs", "debug"),
    ("pathly/explorations", "explore"),
]

# Direct children of pathly/ that are containers, not features.
_RESERVED = {
    "features", "project", "plans", "debugs", "explorations", "fixes",
    "goals", "lessons", "board-artifacts", "pipeline-walkthrough", ".archive",
}


def iter_state_files(cwd: Path) -> Iterator[tuple[Path, str, str]]:
    """Yield ``(state_file, flow, topic)`` for every feature across all three layouts.
    De-duplicates by resolved path; skips ``.archive`` and reserved container dirs."""
    seen: set[str] = set()
    triples: list[tuple[Path, str, str]] = []

    # feature-centric: pathly/features/<name>/plans/STATE.json  → topic = <name>
    features = cwd / "pathly" / "features"
    if features.is_dir():
        for sf in features.glob("*/plans/STATE.json"):
            triples.append((sf, "team", sf.parent.parent.name))

    # legacy type-nested roots  → topic = parent.name
    for root_rel, flow in SCAN_ROOTS:
        root = cwd / root_rel
        if root.is_dir():
            for sf in root.glob("*/STATE.json"):
                triples.append((sf, flow, sf.parent.name))

    # legacy flat: pathly/<name>/STATE.json  → topic = parent.name
    pathly = cwd / "pathly"
    if pathly.is_dir():
        for sf in pathly.glob("*/STATE.json"):
            if sf.parent.name not in _RESERVED:
                triples.append((sf, "team", sf.parent.name))

    for sf, flow, topic in triples:
        if ".archive" in sf.parts:
            continue
        key = str(sf.resolve())
        if key in seen:
            continue
        seen.add(key)
        yield sf, flow, topic


def find_most_recent_state(cwd: Path) -> tuple[Path, str, str] | None:
    """``(storage_path, topic, flow)`` for the most-recently-modified feature, or None."""
    best_mtime = -1.0
    best: tuple[Path, str, str] | None = None
    for state_file, flow, topic in iter_state_files(cwd):
        try:
            mtime = state_file.stat().st_mtime
        except OSError:
            continue
        if mtime > best_mtime:
            best_mtime = mtime
            best = (state_file.parent, topic, flow)
    return best


def find_topic_dir(cwd: Path, topic: str) -> tuple[Path, str] | None:
    """``(storage_path, flow)`` for a named topic — feature-centric first, then legacy
    flat, then the type-nested roots."""
    feat = cwd / "pathly" / "features" / topic / "plans"
    if (feat / "STATE.json").exists():
        return feat, "team"
    flat = cwd / "pathly" / topic
    if (flat / "STATE.json").exists():
        return flat, "team"
    for root_rel, flow in SCAN_ROOTS:
        candidate = cwd / root_rel / topic
        if (candidate / "STATE.json").exists():
            return candidate, flow
    return None
