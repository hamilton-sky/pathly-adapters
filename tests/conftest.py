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


@pytest.fixture(autouse=True)
def _isolate_db(tmp_path, monkeypatch):
    """Redirect ~/.pathly/pathly.db to a per-test temp dir for isolation.

    Patches Path.home() so get_db() writes to tmp_path/.pathly/pathly.db.
    Clears the db connection cache before and after each test.
    """
    import pathly_orchestrator.db as _db

    fake_home = tmp_path
    (fake_home / ".pathly").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    with _db._cache_lock:
        _db._conn_cache.clear()
        _db._write_locks.clear()

    yield

    with _db._cache_lock:
        for conn in _db._conn_cache.values():
            try:
                conn.close()
            except Exception:
                pass
        _db._conn_cache.clear()
        _db._write_locks.clear()
