"""Shared, depth-independent path anchors for the test suite.

Tests live in domain subfolders under ``tests/`` (e.g. ``tests/comms_board/``).
Any test that locates a file inside the repo must resolve the repo root WITHOUT
assuming how deeply it is nested — so this module walks up to the
``pyproject.toml`` marker instead of hard-coding ``Path(__file__).parent.parent``
(which silently pointed at ``tests/`` instead of the repo root once files moved
into subfolders).

Importable as ``from _paths import REPO_ROOT`` from any subfolder: ``conftest.py``
(which never moves) puts ``tests/`` on ``sys.path`` before any test module is
collected. Function-scoped tests can use the ``repo_root`` / ``snapshot_dir``
fixtures from ``conftest.py`` instead.
"""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Return the repo root by walking up from ``start`` to the pyproject marker."""
    here = (start or Path(__file__)).resolve()
    for parent in (here, *here.parents):
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError(f"repo root not found (no pyproject.toml above {here})")


REPO_ROOT = find_repo_root()
SRC = REPO_ROOT / "src"
SNAPSHOT_DIR = REPO_ROOT / "tests" / "snapshots"
