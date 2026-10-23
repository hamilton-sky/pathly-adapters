"""The one guard against a chief watcher that outlives its test (chief-agent 21).

``open_chief`` starts a watcher thread, ``chief-watch-<run id>``, that waits up to 30 seconds for
the tab to report that it started. A test that opens a chief and ends leaves it waiting, and it
wakes in a later test, with the home that test patched gone, and opens the developer's real
``~/.pathly`` (see the comment on ``_isolate_db`` in ``tests/conftest.py``). The same goes for the
two mirror flusher threads, which outlive every test: one that wakes with a mark still queued opens
the database of the unpatched home.

``_no_watcher_outlives_its_test`` is the autouse fixture that closes this. When the test is over
and the patched home is still in place it

1. closes every chief that is still open (``close_chief``), which ends its watcher;
2. waits for the threads this test started (a watcher, a board run, the worker that reads the
   agent's answer, a fake spawn host) to end, and fails the test if one is still alive;
3. fails the test if it left a board lock held that was not held when it began (a scenario that
   takes a lock releases it in its own teardown; the guard never clears one, and a lock an earlier
   test left behind is not blamed on this one);
4. drains the two mirrors while the test's database is still the current one.

An autouse fixture does something only in a test module that imports it BY NAME, so every module
that opens a chief imports ``_no_watcher_outlives_its_test`` (directly or from a support module
that does); ``tests/consistency/test_chief_tests_use_the_guard.py`` fails for one that does not.
``tests/`` is on ``sys.path``, so every domain folder can import this module like ``_paths``.
"""

from __future__ import annotations

import threading
import time

import pytest
from mirror_drain_support import drain_mirrors

WATCHER_PREFIX = "chief-watch-"
# Threads a worker spawn starts, and the ones the chief tests start. A name here that a test
# started and left alive fails it.
WORKER_THREADS = ("board-run-", "agent-done-watcher-")
STARTED_BY_TESTS = (
    WATCHER_PREFIX,
    *WORKER_THREADS,
    "fake-spawn-host",
    "asker-",
    "acceptance-server",
)
WAIT_SECONDS = 5.0


def _named(prefixes: tuple[str, ...]) -> list[threading.Thread]:
    return [
        t for t in threading.enumerate() if t.is_alive() and t.name.startswith(prefixes)
    ]


def _started_since(before: set[threading.Thread]) -> list[threading.Thread]:
    return [t for t in _named(STARTED_BY_TESTS) if t not in before]


def close_open_chiefs() -> None:
    """Close the chief of every watcher thread that is alive (a no-op for one already closed)."""
    from pathly_orchestrator.supervisor.chief_session import close_chief

    for thread in _named((WATCHER_PREFIX,)):
        close_chief(thread.name[len(WATCHER_PREFIX) :], "test over")


@pytest.fixture(autouse=True)
def _no_watcher_outlives_its_test(request):
    """Close the chiefs a test left open while its database and sessions folder are still
    patched in, then fail the test if a thread it started is alive or a board lock is held, and
    drain the two mirrors. See the module docstring."""
    try:
        # The module's own ``chief_root`` (it moves the sessions folder): asked for here, it is
        # put back only after this teardown, as every test of such a module has always had it.
        request.getfixturevalue("chief_root")
    except pytest.FixtureLookupError:
        pass
    from pathly_orchestrator.supervisor import board_lock

    before = set(_named(STARTED_BY_TESTS))
    held_before = dict(board_lock._held)
    yield

    close_open_chiefs()
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline and _started_since(before):
        time.sleep(0.01)
    left = [t.name for t in _started_since(before)]
    left_held = {
        board: run_id
        for board, run_id in dict(board_lock._held).items()
        if held_before.get(board) != run_id
    }
    drain_mirrors()
    assert left == [], f"threads outlived the test: {left}"
    assert left_held == {}, f"board locks the test left held: {left_held}"
