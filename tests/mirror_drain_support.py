"""Drains the two mirror flusher threads at the end of a test (chief-agent 20).

``board-mirror-flusher`` and ``event-mirror-flusher`` are daemon threads that outlive every test.
A route that posts a message queues a mark, and a flusher that wakes after the test is over opens
``~/.pathly/pathly.db`` and writes ``global/BOARD.json`` of the home the test no longer patches.
``_mirrors_are_drained`` flushes both while the test's database is still the current one; a test
module imports it by name (an autouse fixture in a module that is not imported does nothing).
``tests/`` is on ``sys.path``, so every domain folder can import this module.
"""

from __future__ import annotations

import pytest


def drain_mirrors() -> None:
    from pathly_orchestrator import board_mirror, event_mirror
    from pathly_orchestrator.db.connection import get_db

    board_mirror.flush_dirty(get_db())
    event_mirror.flush_dirty(get_db())


@pytest.fixture(autouse=True)
def _mirrors_are_drained():
    yield
    drain_mirrors()
