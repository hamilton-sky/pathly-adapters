"""Test fixtures that keep temporary files inside the repository workspace."""

import os
import shutil
import sys
import tempfile
from pathlib import Path

# Put tests/ on sys.path (before any test module is collected) so tests in domain
# subfolders can `from _paths import REPO_ROOT`. conftest.py lives at tests/ root and
# never moves, so this anchor is stable regardless of how deeply a test is nested.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import _paths  # noqa: E402  (depends on the sys.path insert above)

# The FSM server's default port (``config.DEFAULT_FSM_PORT``; not imported, so the package is
# not loaded before the tests patch it). When Studio runs, a live server listens there.
LIVE_FSM_PORT = 8765
_LOOPBACK = ("::1", "localhost", "0.0.0.0", "::ffff:127.0.0.1")
FSM_SERVER_MODULE = "pathly_orchestrator.http_server"


def _no_live_fsm_server(event: str, args: tuple) -> None:
    """Keep the test process away from the developer's FSM server, as if none were running.

    The supervisor loop calls ``/next_action`` on 127.0.0.1:8765 through ``fsm_http_client``;
    when nothing answers, ``ensure_server_running`` starts ``python -m
    pathly_orchestrator.http_server`` detached from the test process, with the real HOME. A
    test that leaves a real loop running (one did) then wrote a fake goal run into the
    developer's live server, or left a server of its own running after pytest. This refuses
    both: a connection to a loopback address on 8765 fails as a refused connection, and
    starting the server module fails as an ``OSError``, so the client falls back to running
    the FSM in process (``fsm_http_client._inprocess``). A test that needs a server starts its
    own on a free port. Audit hooks see calls made in this process only, not in a child.
    """
    if event == "socket.connect":
        address = args[1] if len(args) > 1 else None
        if (
            isinstance(address, tuple)
            and len(address) >= 2
            and address[1] == LIVE_FSM_PORT
            and isinstance(address[0], str)
            and (address[0].startswith("127.") or address[0] in _LOOPBACK)
        ):
            raise ConnectionRefusedError(
                f"tests/conftest.py: tests do not connect to the FSM server on "
                f"{address[0]}:{LIVE_FSM_PORT}"
            )
    elif event == "subprocess.Popen":
        argv = args[1] if len(args) > 1 else None
        if isinstance(argv, (list, tuple)):
            words = [str(a) for a in argv]
            starts_server = any(
                words[i] == "-m" and words[i + 1] == FSM_SERVER_MODULE
                for i in range(len(words) - 1)
            ) or (words and os.path.basename(words[0]) == "pathly-fsm-http")
            if starts_server:
                raise PermissionError(
                    "tests/conftest.py: tests do not start the FSM server process"
                )


sys.addaudithook(_no_live_fsm_server)


def _tmp_root() -> Path:
    default_root = r"C:\tmp" if os.name == "nt" else tempfile.gettempdir()
    tmp_root = Path(os.environ.get("PYTEST_TMPDIR", default_root)).resolve()
    tmp_root = tmp_root / "pathly-tests"
    tmp_root.mkdir(parents=True, exist_ok=True)
    return tmp_root


_session_home: Path | None = None


def pytest_configure(config):
    """Point ``Path.home()`` at a throwaway home for the whole test process.

    ``_isolate_db`` patches ``Path.home()`` for each test and restores it at teardown,
    so between two tests it answered the developer's real home. A thread that outlives
    its test (the board and event mirror flushers run for the life of the process) then
    opened the real ``~/.pathly/pathly.db``, migrated it and wrote to it. With this in
    place the per-test patch restores to the throwaway home, never the real one. It is
    never undone: a daemon thread can still run while the process exits.
    """
    global _session_home
    _session_home = Path(tempfile.mkdtemp(prefix="session-home-", dir=_tmp_root()))
    (_session_home / ".pathly").mkdir()
    home = _session_home.resolve()
    Path.home = staticmethod(lambda: home)


def pytest_unconfigure(config):
    if _session_home is not None:
        shutil.rmtree(_session_home, ignore_errors=True)


@pytest.fixture
def tmp_path():
    """Workspace-safe replacement for pytest's default temp path fixture.

    The root is RESOLVED (symlinks followed) before any test sees it. On macOS
    ``tempfile.gettempdir()`` returns ``/var/folders/…``, and ``/var`` is a symlink to
    ``/private/var`` — so a test that WRITES through production code (which resolves
    real paths) and then READS with the raw fixture path is comparing
    ``/private/var/…`` against ``/var/…`` and silently misses. That mismatch failed 19
    tests across fsm_flows, runner_supervisor, http_api and storage_paths on macOS
    while passing on Windows, where ``C:\\tmp`` is not a symlink. Resolving here fixes
    every one of them at the source instead of sprinkling ``.resolve()`` through the
    assertions.
    """
    path = Path(tempfile.mkdtemp(dir=_tmp_root())).resolve()
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

    def _drop_pending_mirror_writes():
        # The mirror flushers live for the whole process: a board or event log this test
        # left dirty would be written on their next tick, into whichever home and project
        # folders exist then (a later test's, or a deleted temp dir they recreate).
        from pathly_orchestrator import board_mirror, event_mirror

        for mirror in (board_mirror, event_mirror):
            with mirror._dirty_lock:
                mirror._dirty.clear()

    _reset_conn_state()
    yield
    _drop_pending_mirror_writes()
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


@pytest.fixture
def repo_root() -> Path:
    """Absolute repo root (pyproject.toml marker) — depth-independent.

    Prefer this over ``Path(__file__).parent.parent`` in new tests: it resolves
    correctly no matter which domain subfolder the test lives in.
    """
    return _paths.REPO_ROOT


@pytest.fixture
def snapshot_dir() -> Path:
    """Absolute path to tests/snapshots/ (compose snapshot fixtures)."""
    return _paths.SNAPSHOT_DIR
