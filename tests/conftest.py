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
    import pathly_orchestrator.db.connection as _conn_mod

    fake_home = tmp_path
    (fake_home / ".pathly").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    # Reset per-thread connection and one-time init flag so each test gets a fresh DB.
    if hasattr(_conn_mod._local, "conn") and _conn_mod._local.conn is not None:
        try:
            _conn_mod._local.conn.close()
        except Exception:
            pass
        _conn_mod._local.conn = None
    with _conn_mod._write_locks_meta:
        _conn_mod._write_locks.clear()
    _conn_mod._init_once_done = False

    yield

    # Cleanup after test.
    if hasattr(_conn_mod._local, "conn") and _conn_mod._local.conn is not None:
        try:
            _conn_mod._local.conn.close()
        except Exception:
            pass
        _conn_mod._local.conn = None
    with _conn_mod._write_locks_meta:
        _conn_mod._write_locks.clear()
    _conn_mod._init_once_done = False
