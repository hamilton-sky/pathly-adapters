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
def _no_async_embed(monkeypatch, request):
    """Disable the background embedding thread for all tests.

    embed_async() spawns a daemon thread that opens its own connection and
    writes embeddings concurrently — it races the per-test DB and causes
    intermittent 'database is locked' failures in the concurrency tests.
    """
    if request.node.get_closest_marker("no_pathly_autouse"):
        yield
        return
    try:
        import pathly_orchestrator.runner.embeddings as _emb_mod

        monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)
    except Exception:
        pass
    yield


@pytest.fixture(autouse=True)
def _isolate_db(monkeypatch, request):
    """Redirect ~/.pathly/pathly.db to a per-test temp dir for isolation.

    Patches Path.home() so get_db() writes to tmp_path/.pathly/pathly.db.
    Clears the db connection cache before and after each test.
    """
    if request.node.get_closest_marker("no_pathly_autouse"):
        yield
        return
    import pathly_orchestrator.db.connection as _conn_mod

    tmp_path = request.getfixturevalue("tmp_path")
    fake_home = tmp_path
    (fake_home / ".pathly").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    def _reset_conn_state():
        # Drop the MAIN-thread cached connection and ALL per-path / one-time init state so
        # each test starts against a pristine, unprepared DB. This resets only the CURRENT
        # thread's connection — the real cross-test fix lives in connection.get_db(), which
        # reopens ANY thread's connection when the resolved db_path changes, so a leftover
        # daemon thread can no longer migrate one test's db while marking another prepared.
        # Clearing _prepared_paths keeps the "fresh DB per test" contract complete: without
        # it the set just grows one entry per test (harmless, since paths are unique).
        conn = getattr(_conn_mod._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        _conn_mod._local.conn = None
        _conn_mod._local.conn_path = None
        _conn_mod._init_once_done = False
        _conn_mod._prepared_paths.clear()

    _reset_conn_state()
    yield
    _reset_conn_state()


@pytest.fixture(autouse=True)
def _reset_rate_limiter(request):
    """Clear the module-level per-IP rate-limit counters around each test.

    `middleware._rate_counters` is a global deque keyed by client IP and is NOT
    reset between tests; rate limiting is on by default (PATHLY_FF_RATE_LIMITING
    defaults True). A large test group (e.g. all tests/test_comms_*) therefore
    accumulates >120 requests per IP inside the 60s window and every later request
    429s — which made write_perm/tasks_claim_fail pass alone but fail in the group.
    Clearing per test fixes that; the dedicated rate-limit tests in test_http_server
    still trip the limit because they make their own 120+ requests after this reset.
    """

    if request.node.get_closest_marker("no_pathly_autouse"):
        yield
        return

    def _clear():
        try:
            from pathly_orchestrator.http_server import middleware as _mw

            with _mw._rate_lock:
                _mw._rate_counters.clear()
        except Exception:
            pass

    _clear()
    yield
    _clear()
