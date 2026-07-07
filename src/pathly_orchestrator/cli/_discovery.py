"""Shared feature-discovery for the pathly-* CLI shortcuts (status / ff / back / log).

Covers the storage layouts so a feature/run is found wherever it lives:
  - feature-centric flat (current):   pathly/features/<name>/STATE.json
  - board-scoped nested run (current): pathly/features/<f>/<kind>/<slug>/STATE.json
                                       pathly/project/<kind>/<slug>/STATE.json
  - feature-centric nested (legacy):  pathly/features/<name>/plans/STATE.json
  - type-nested (legacy):             pathly/plans|debugs|explorations/<name>/STATE.json
  - flat (legacy):                    pathly/<name>/STATE.json

Reserved container dirs under pathly/ are skipped; results de-dupe by resolved path.
Each result carries its own ``topic`` (the FEATURE name) because it is NOT always
``state_file.parent.name`` — for the nested feature-centric layout the name is the
grandparent (``pathly/features/<name>/plans/``), not the immediate parent (``plans``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

# (relative root, flow label) for the legacy type-nested layout. debugs/explorations stay here for
# back-compat DISCOVERY of runs still sitting in the old top-level buckets; they get retired only
# once board-scoped-storage P2 MOVES those runs under their board (retiring the root before the move
# would make the still-present runs invisible — the P2<->P3 coupling). New/moved runs are found by
# the board-scoped globs in iter_state_files below.
SCAN_ROOTS = [
    ("pathly/plans", "team"),
    ("pathly/debugs", "debug"),
    ("pathly/explorations", "explore"),
]

# Run kinds and their flow label, for board-scoped nested discovery
# (pathly/features/<f>/<kind>/<slug> and pathly/project/<kind>/<slug>).
_KIND_FLOW = (
    ("goals", "team"),
    ("debugs", "debug"),
    ("explorations", "explore"),
    ("fixes", "quick-fix"),
)

# Direct children of pathly/ that are containers, not features.
_RESERVED = {
    "features",
    "project",
    "plans",
    "debugs",
    "explorations",
    "fixes",
    "goals",
    "lessons",
    "board-artifacts",
    "pipeline-walkthrough",
    ".archive",
}


def iter_state_files(cwd: Path) -> Iterator[tuple[Path, str, str]]:
    """Yield ``(state_file, flow, topic)`` for every feature across all three layouts.
    De-duplicates by resolved path; skips ``.archive`` and reserved container dirs."""
    seen: set[str] = set()
    triples: list[tuple[Path, str, str]] = []

    # feature-centric flat (current):   pathly/features/<name>/STATE.json        → topic = <name>
    # feature-centric nested (legacy):  pathly/features/<name>/plans/STATE.json  → topic = <name>
    features = cwd / "pathly" / "features"
    if features.is_dir():
        for sf in features.glob("*/STATE.json"):
            triples.append((sf, "team", sf.parent.name))
        for sf in features.glob("*/plans/STATE.json"):
            triples.append((sf, "team", sf.parent.parent.name))
        # board-scoped nested runs: features/<f>/<kind>/<slug>/STATE.json → topic = <slug>
        for kind, flow in _KIND_FLOW:
            for sf in features.glob(f"*/{kind}/*/STATE.json"):
                triples.append((sf, flow, sf.parent.name))

    # project board: pathly/project/<kind>/<slug>/STATE.json → topic = <slug>
    project = cwd / "pathly" / "project"
    if project.is_dir():
        for kind, flow in _KIND_FLOW:
            for sf in (project / kind).glob("*/STATE.json"):
                triples.append((sf, flow, sf.parent.name))

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
    """``(storage_path, flow)`` for a named topic — feature-centric (flat, then nested)
    first, then legacy flat, then the type-nested roots."""
    feat_flat = cwd / "pathly" / "features" / topic
    if (feat_flat / "STATE.json").exists():
        return feat_flat, "team"
    feat = cwd / "pathly" / "features" / topic / "plans"
    if (feat / "STATE.json").exists():
        return feat, "team"
    flat = cwd / "pathly" / topic
    if (flat / "STATE.json").exists():
        return flat, "team"
    # board-scoped project runs: pathly/project/<kind>/<topic>/STATE.json
    for kind, flow in _KIND_FLOW:
        cand = cwd / "pathly" / "project" / kind / topic
        if (cand / "STATE.json").exists():
            return cand, flow
    for root_rel, flow in SCAN_ROOTS:
        candidate = cwd / root_rel / topic
        if (candidate / "STATE.json").exists():
            return candidate, flow
    return None
