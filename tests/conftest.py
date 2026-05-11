"""Test fixtures that keep temporary files inside the repository workspace."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_path():
    """Workspace-safe replacement for pytest's default temp path fixture."""
    default_root = r"C:\tmp" if os.name == "nt" else tempfile.gettempdir()
    tmp_root = Path(os.environ.get("PYTEST_TMPDIR", default_root))
    tmp_root = tmp_root / "pathly-tests"
    tmp_root.mkdir(parents=True, exist_ok=True)
    path = Path(tempfile.mkdtemp(dir=tmp_root))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)
