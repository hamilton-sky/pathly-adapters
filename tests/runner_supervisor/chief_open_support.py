"""Shared fixtures of the tests that open a chief through ``open_chief`` (chief-agent 20).

``Host`` stands in for the spawn host (it only records what it is sent), ``chief_root`` points
the sessions folder at a temp dir, and the autouse ``_no_watcher_outlives_its_test`` closes every
chief a test left open while its DB and folder are still patched in, then drains the two mirror
flusher threads (they outlive every test; one that wakes between two tests with a mark still
queued opens the DB of the unpatched home). A test module has to import that fixture by name, or
pytest never runs it. Imported by bare name: ``tests/`` is on ``sys.path``.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from mirror_drain_support import drain_mirrors

from pathly_orchestrator.supervisor import chief_session
from pathly_orchestrator.supervisor.chief_session import close_chief, open_chief

PROMPT = "---\ntier: operator\n---\nYou are the chief of this project."
WATCHER_PREFIX = "chief-watch-"


class Host:
    """The spawn host's side of the contract: it only records what it was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def __call__(self, topic: str, payload: dict) -> None:
        self.sent.append((topic, payload))


@pytest.fixture()
def project(tmp_path: Path) -> str:
    root = tmp_path / "proj"
    root.mkdir()
    return str(root)


@pytest.fixture()
def chief_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "chief sessions"
    monkeypatch.setattr(chief_session, "_chief_root", lambda: root)
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", "8123")
    return root


def wait(done, seconds: float = 5.0) -> bool:
    """A bounded poll on the monotonic clock (not a patched sleep)."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if done():
            return True
        time.sleep(0.01)
    return done()


def watchers() -> list[threading.Thread]:
    return [t for t in threading.enumerate() if t.name.startswith(WATCHER_PREFIX)]


@pytest.fixture(autouse=True)
def _no_watcher_outlives_its_test(chief_root: Path):
    yield
    for thread in watchers():
        close_chief(thread.name[len(WATCHER_PREFIX) :], "test over")
    assert wait(lambda: not watchers()), [t.name for t in watchers()]
    drain_mirrors()


def open_with(project: str, host: Host, **overrides) -> dict:
    """``open_chief`` for an operator on claude; ``overrides`` replace any argument (the engine too)."""
    args = dict(
        project_root=project,
        engine="claude",
        preset="operator",
        prompt=PROMPT,
        broadcast_fn=host,
    )
    args.update(overrides)
    return open_chief(**args)
