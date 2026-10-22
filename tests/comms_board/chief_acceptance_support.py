"""Helpers of the chief acceptance test (chief-agent 13).

``SpawnHost`` stands in for Studio's terminal listener: a thread that reads a queue registered in
``sse._spawn_clients``, which is what an ``/events/spawn`` client gets, and records every payload
as that stream carries it, the raw ``run_token`` included. For a chief's tab it reports the tab
started (what ``/runner/terminal/started`` does). For a worker spawn it first looks its token up
while the run is alive, then reports the run started and, unless the test holds it, finished,
which makes the supervisor's spawn settle and revoke the token (the way
``test_rrp_acceptance.py`` finishes a stage). The real ``_broadcast_runner`` is used, so the
queues see exactly what the server sends. ``Asker`` is a registered run whose stage waits in
``_await_agent_question``. ``type_in_tab`` is the chief hook's own request, so the messages a
chief may cite are recorded by the real route. The autouse guard closes every chief a test left
open (its watcher thread would wake 30 seconds later, in a later test, with no patched home) and
fails the test when a thread it started is still alive. Imported by bare name: ``tests/comms_board``
is on ``sys.path`` for the test files that sit in it.
"""

from __future__ import annotations

import json
import queue
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, NamedTuple

import pytest
from _paths import SRC
from chief_session_guard import (
    STARTED_BY_TESTS,
    WORKER_THREADS,
    _no_watcher_outlives_its_test,
)

FRAGMENT_PATH = (
    SRC / "pathly_data" / "core" / "skills" / "fragments" / "chief-connect.md"
)
TOKEN_HEADER = "X-Pathly-Run-Token"
WAIT = 15.0


def wait_for(condition: Callable[[], object], what: str, timeout: float = WAIT):
    """The first truthy value ``condition`` returns, or a failure naming ``what``."""
    deadline = time.monotonic() + timeout
    while True:
        found = condition()
        if found:
            return found
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.01)


def live_threads() -> list[threading.Thread]:
    return [
        t
        for t in threading.enumerate()
        if t.is_alive() and t.name.startswith(STARTED_BY_TESTS)
    ]


class Worker(NamedTuple):
    """One worker spawn: the payload as ``/events/spawn`` carried it and what its token resolved
    to, looked up by the host while the run was alive."""

    payload: dict
    live: dict | None


class SpawnHost:
    def __init__(self) -> None:
        self.inbox: queue.Queue = queue.Queue()
        self.tabs: dict[str, dict] = {}
        self.workers: dict[str, Worker] = {}
        self.kills: list[dict] = []
        self.errors: list[BaseException] = []
        self.hold = False
        self._thread = threading.Thread(
            target=self._loop, name="fake-spawn-host", daemon=True
        )

    # -- lifecycle --------------------------------------------------------------------

    def start(self) -> None:
        from pathly_orchestrator.http_server import sse

        with sse._spawn_lock:
            sse._spawn_clients.append(self.inbox)
        self._thread.start()

    def stop(self) -> None:
        from pathly_orchestrator.http_server import sse

        for run_id in list(self.workers):
            self.finish(run_id)
        wait_for(
            lambda: not [
                t for t in live_threads() if t.name.startswith(WORKER_THREADS)
            ],
            "the worker spawns to end",
        )
        with sse._spawn_lock:
            if self.inbox in sse._spawn_clients:
                sse._spawn_clients.remove(self.inbox)
        self.inbox.put(None)
        self._thread.join(timeout=WAIT)
        assert not self._thread.is_alive(), "the fake spawn host did not stop"
        assert self.errors == [], self.errors

    # -- the host thread --------------------------------------------------------------

    def _loop(self) -> None:
        while True:
            raw = self.inbox.get()
            if raw is None:
                return
            try:
                self._handle(json.loads(raw))
            except BaseException as exc:  # reported by stop(), never swallowed
                self.errors.append(exc)

    def _handle(self, payload: dict) -> None:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.run_tokens import resolve_run_token
        from pathly_orchestrator.supervisor.registry import get_run

        kind, run_id = payload.get("type"), payload.get("run_id")
        if kind == "TERMINAL_KILL":
            self.kills.append(payload)
            return
        if kind != "TERMINAL_SPAWN":
            return
        run = get_run(run_id)
        assert run is not None, f"no run is registered for the spawn of {run_id}"
        if payload.get("interactive"):
            self.tabs[run_id] = payload
            run.mark_started()
            return
        # Resolve the token while the run is alive: the spawn revokes it when it settles.
        live = resolve_run_token(get_db(), payload.get("run_token"))
        self.workers[run_id] = Worker(payload, live)
        run.mark_started()
        if not self.hold:
            self.finish(run_id)

    # -- what a test asks of it -------------------------------------------------------

    def finish(self, run_id: str) -> None:
        """Report the worker's process exited 0 (no-op once the run has settled)."""
        from pathly_orchestrator.supervisor.registry import get_run

        run = get_run(run_id)
        if run is not None:
            run.mark_pty_result({"result": {}, "exit_code": 0})

    def tab(self, run_id: str) -> dict:
        return wait_for(lambda: self.tabs.get(run_id), f"the tab spawn of {run_id}")

    def worker(self, run_id: str) -> Worker:
        return wait_for(lambda: self.workers.get(run_id), f"the spawn of {run_id}")

    def settle(self, run_id: str) -> None:
        """Wait until the run's spawn has returned: its thread ended, so its token is revoked."""
        name = f"board-run-{run_id[:8]}"
        wait_for(
            lambda: not any(t.name == name for t in live_threads()),
            f"the spawn of {run_id} to end",
        )


@pytest.fixture()
def spawn_host() -> Iterator[SpawnHost]:
    host = SpawnHost()
    host.start()
    try:
        yield host
    finally:
        host.stop()


# -- the app, a project, a chief -----------------------------------------------------------


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A project with one feature, ``demo`` (a feature row is a project's own only when its
    folder exists there)."""
    root = tmp_path / "proj"
    (root / "pathly" / "features" / "demo").mkdir(parents=True)
    return root


@pytest.fixture()
def other_project(tmp_path: Path) -> Path:
    root = tmp_path / "elsewhere"
    root.mkdir()
    return root


@pytest.fixture(autouse=True)
def _no_embedding_model(monkeypatch: pytest.MonkeyPatch):
    """No embedding model: a prompt's board context falls back to recency."""
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(emb, "embed", lambda *a, **k: None)


class Chief(NamedTuple):
    """A chief opened through ``POST /chief/open``: the route's answer and the spawn the host
    received for its tab."""

    answer: dict
    tab: dict

    @property
    def run_id(self) -> str:
        return self.answer["run_id"]

    @property
    def token(self) -> str:
        return self.tab["run_token"]

    @property
    def headers(self) -> dict:
        return {TOKEN_HEADER: self.token}


def open_chief(client, host: SpawnHost, root: Path, preset: str, **extra) -> Chief:
    body = {"project_root": str(root), "engine": "claude", "preset": preset, **extra}
    resp = client.post("/chief/open", json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    answer = resp.get_json()
    return Chief(answer, host.tab(answer["run_id"]))


def session_row(run_id: str) -> dict:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.chief import get_session

    found = get_session(get_db(), run_id)
    assert found is not None
    return found


def type_in_tab(client, chief: Chief, text: str, relayed: bool = False) -> dict:
    """What the chief's UserPromptSubmit hook posts when ``text`` is submitted in the tab
    (``relayed`` is the hook's flag for a prompt that another session or a task notification
    delivered)."""
    from pathly_orchestrator.supervisor.chief_session import _chief_root

    secret = (_chief_root() / chief.run_id / "hook_secret").read_text(encoding="utf-8")
    body = {
        "run_id": chief.run_id,
        "hook_secret": secret,
        "session_id": session_row(chief.run_id)["cli_session_id"],
        "text": text,
        "relayed": relayed,
    }
    resp = client.post("/chief/human-messages", json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def paste_prompt(client, chief: Chief) -> None:
    """The host pastes the prompt and the person submits it: the session's first message, which
    is the style prompt and so never citable."""
    stored = type_in_tab(client, chief, chief.tab["prompt"])
    assert stored["kind"] == "style_prompt"


def later() -> None:
    """Let the clock move on, so a message and a question are never stamped alike."""
    time.sleep(0.02)


def db():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


# -- a real server -------------------------------------------------------------------------


@contextmanager
def serving() -> Iterator[int]:
    """The app on a free port, for a process that cannot use the test client."""
    from werkzeug.serving import make_server

    from pathly_orchestrator.http_server import app

    httpd = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(
        target=httpd.serve_forever, name="acceptance-server", daemon=True
    )
    thread.start()
    try:
        yield httpd.server_port
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=WAIT)
        assert not thread.is_alive()
