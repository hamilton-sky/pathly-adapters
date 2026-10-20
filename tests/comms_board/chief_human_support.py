"""Shared fixtures and helpers of the chief human-message tests (chief-agent 09).

``open_session`` opens a chief through ``open_chief`` with a fake broadcaster (it only records
the spawn), so the secret is the one in the session folder and the session id is the stored
``cli_session_id``, exactly what the real hook sees. The fixtures (and the autouse one that
closes a chief's watcher thread) are imported by name into each ``test_chief_*`` file that uses
them; ``FakeServer`` stands in for ``fsm_http_client._request_json``.
"""

from __future__ import annotations

import io
import json
import sys
import threading
import time
from pathlib import Path
from typing import NamedTuple

import pytest

from pathly_hooks import chief_prompt
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as chief_queries
from pathly_orchestrator.http_server import sse
from pathly_orchestrator.supervisor import chief_session
from pathly_orchestrator.supervisor.chief_session import close_chief, open_chief

PROMPT = "---\ntier: operator\n---\nYou are the chief of this project."
SESSION_ID = "0b1f2a3c-4d5e-4f60-8a7b-9c0d1e2f3a4b"
RUN_ID = "chief-aaaaaaaaaaaa"
# What a message another claude session sends arrives as, measured on claude 2.1.304.
WRAPPED = (
    '<cross-session-message from="uds:/tmp/cc-socks/952.sock" from-name="worker"'
    ' from-mode="prompting">\nRELAYED-TEST hello from another session\n'
    "</cross-session-message>"
)


class Host:
    """The spawn host's side of the contract: it only records what it was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def __call__(self, topic: str, payload: dict) -> None:
        self.sent.append((topic, payload))


class Opened(NamedTuple):
    run_id: str
    secret: str
    cli_session_id: str
    run_token: str
    project: str


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


@pytest.fixture()
def host(monkeypatch: pytest.MonkeyPatch) -> Host:
    fake = Host()
    monkeypatch.setattr(sse, "_broadcast_runner", fake)
    return fake


@pytest.fixture(autouse=True)
def _no_watcher_outlives_its_test(chief_root: Path):
    """A chief a test leaves open has a watcher waiting; close it while this test's DB and
    sessions folder are still patched in."""
    yield
    prefix = "chief-watch-"
    for thread in threading.enumerate():
        if thread.name.startswith(prefix):
            close_chief(thread.name[len(prefix) :], "test over")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and any(
        t.name.startswith(prefix) for t in threading.enumerate()
    ):
        time.sleep(0.01)


@pytest.fixture()
def client(host: Host):
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def open_session(project: str, chief_root: Path, preset: str = "operator") -> Opened:
    spawn = Host()
    result = open_chief(
        project_root=project,
        engine="claude",
        preset=preset,
        prompt=PROMPT,
        broadcast_fn=spawn,
    )
    run_id = result["run_id"]
    session = chief_queries.get_session(get_db(), run_id)
    secret = (chief_root / run_id / "hook_secret").read_text(encoding="utf-8")
    token = spawn.sent[0][1]["run_token"]
    return Opened(run_id, secret, session["cli_session_id"], token, project)


def body_of(opened: Opened, **overrides) -> dict:
    body = {
        "run_id": opened.run_id,
        "hook_secret": opened.secret,
        "text": "use CSV",
        "session_id": opened.cli_session_id,
    }
    body.update(overrides)
    return body


def rows_of(run_id: str) -> list[tuple[str, str]]:
    cur = get_db().execute(
        "SELECT kind, text FROM chief_human_messages WHERE run_id = ? ORDER BY id",
        (run_id,),
    )
    return [(r[0], r[1]) for r in cur.fetchall()]


class FakeServer:
    """Stands in for ``_request_json``: records the call, answers or raises."""

    def __init__(self, reply=None, error: BaseException | None = None) -> None:
        self.reply = reply
        self.error = error
        self.calls: list[tuple] = []

    def __call__(self, method, path, payload, **kwargs):
        self.calls.append((method, path, payload, kwargs))
        if self.error is not None:
            raise self.error
        return self.reply


@pytest.fixture()
def secret_file(tmp_path: Path) -> Path:
    path = tmp_path / "hook_secret"
    path.write_text("s3cret\n", encoding="utf-8")
    return path


def argv_for(secret_file: Path) -> list[str]:
    return ["--run-id", RUN_ID, "--secret-file", str(secret_file), "--port", "8123"]


def stdin_of(prompt="use CSV", session_id=SESSION_ID) -> str:
    """The JSON a UserPromptSubmit hook gets; ``None`` leaves a field out."""
    event = {"hook_event_name": "UserPromptSubmit", "permission_mode": "default"}
    if prompt is not None:
        event["prompt"] = prompt
    if session_id is not None:
        event["session_id"] = session_id
    return json.dumps(event)


def run_hook(monkeypatch, stdin: str, server: FakeServer, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
    monkeypatch.setattr(chief_prompt, "_request_json", server)
    return chief_prompt.main(argv)
