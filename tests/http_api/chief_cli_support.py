"""Helpers of the `pathly api` tests (chief-agent 17).

``server`` is the real Flask app on a free port, behind a wrapper that records every request it
is sent, so a test can say "the server saw no request" and read the headers the command sent.
``pathly`` runs ``chief_cli.main`` in this process with the environment a chief's tab has
(``PATHLY_FSM_HTTP_PORT`` pointing at ``server``, ``PATHLY_RUN_TOKEN`` as the test gives it) and
returns what it exited with and what it printed. ``host`` stands in for the spawn host: it only
records what ``POST /chief/open`` sends it.
"""

from __future__ import annotations

import http.server
import io
import sys
import threading
import time
from typing import NamedTuple

import pytest

from _paths import SRC

FRAGMENT_PATH = (
    SRC / "pathly_data" / "core" / "skills" / "fragments" / "chief-connect.md"
)
MISSING_TOKEN = (
    "PATHLY_RUN_TOKEN is not set: open the chief from Pathly "
    "(a codex shell_environment_policy can also filter it)"
)


class Seen(NamedTuple):
    """One request as the server's wrapper saw it."""

    method: str
    target: str
    run_token: str | None
    secret: str | None
    content_type: str | None


class Recording:
    """A WSGI wrapper: records each request, then hands it to the app unchanged."""

    def __init__(self, app) -> None:
        self.app = app
        self.requests: list[Seen] = []
        self.port = 0

    def __call__(self, environ, start_response):
        query = environ.get("QUERY_STRING")
        self.requests.append(
            Seen(
                environ["REQUEST_METHOD"],
                environ["PATH_INFO"] + (f"?{query}" if query else ""),
                environ.get("HTTP_X_PATHLY_RUN_TOKEN"),
                environ.get("HTTP_X_PATHLY_SECRET"),
                environ.get("CONTENT_TYPE"),
            )
        )
        return self.app(environ, start_response)


@pytest.fixture()
def server(monkeypatch: pytest.MonkeyPatch):
    """The app on a free port; ``PATHLY_FSM_HTTP_PORT`` names it and no secret is set."""
    from werkzeug.serving import make_server

    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    recording = Recording(app)
    httpd = make_server("127.0.0.1", 0, recording, threaded=True)
    recording.port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", str(recording.port))
    monkeypatch.delenv("PATHLY_API_SECRET", raising=False)
    try:
        yield recording
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=10)


class Stub:
    """A server that answers every request with ``status`` and ``body``, and keeps what it got.

    With ``echo_token`` the body is a JSON object holding the run token it was sent, which no
    real route does: it lets a test see that the command keeps its token out of what it prints.
    """

    def __init__(self) -> None:
        self.status = 200
        self.body = b""
        self.echo_token = False
        self.got: list[dict] = []


@pytest.fixture()
def stub(monkeypatch: pytest.MonkeyPatch):
    stub = Stub()

    class Handler(http.server.BaseHTTPRequestHandler):
        def _answer(self) -> None:
            size = int(self.headers.get("content-length") or 0)
            stub.got.append(
                {
                    "method": self.command,
                    "target": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": self.rfile.read(size),
                }
            )
            body = stub.body
            if stub.echo_token:
                token = self.headers.get("X-Pathly-Run-Token", "")
                body = ('{"echo": "%s"}' % token).encode()
            self.send_response(stub.status)
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = do_PUT = do_DELETE = _answer

        def log_message(self, *args) -> None:
            return

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("PATHLY_FSM_HTTP_PORT", str(httpd.server_port))
    monkeypatch.delenv("PATHLY_API_SECRET", raising=False)
    try:
        yield stub
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=10)


class Ran(NamedTuple):
    code: int
    out: str
    err: str


NO_TOKEN = object()


@pytest.fixture()
def pathly(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """``pathly("api", "GET", "/comms", token=...)``: run the command, return ``Ran``.

    ``token`` is the value of ``PATHLY_RUN_TOKEN`` (``NO_TOKEN``, the default, leaves it unset);
    ``stdin`` is what the command may read from standard input: text, or bytes that the stream
    decodes as UTF-8 the way a pipe does (so bytes that are not UTF-8 fail when read).
    """
    from pathly_orchestrator import chief_cli

    def run(*args: str, token=NO_TOKEN, stdin: str | bytes = "") -> Ran:
        if token is NO_TOKEN:
            monkeypatch.delenv("PATHLY_RUN_TOKEN", raising=False)
        else:
            monkeypatch.setenv("PATHLY_RUN_TOKEN", token)
        source = (
            io.TextIOWrapper(io.BytesIO(stdin), encoding="utf-8")
            if isinstance(stdin, bytes)
            else io.StringIO(stdin)
        )
        monkeypatch.setattr(sys, "stdin", source)
        capsys.readouterr()
        code = chief_cli.main(list(args))
        seen = capsys.readouterr()
        return Ran(code, seen.out, seen.err)

    return run


class Host:
    """The spawn host's side of the contract: it only records what it was sent."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, dict]] = []

    def __call__(self, topic: str, payload: dict) -> None:
        self.sent.append((topic, payload))

    @property
    def spawn(self) -> dict:
        spawns = [p for _, p in self.sent if p.get("type") == "TERMINAL_SPAWN"]
        assert len(spawns) == 1, self.sent
        return spawns[0]


@pytest.fixture()
def host(monkeypatch: pytest.MonkeyPatch) -> Host:
    from pathly_orchestrator.http_server import sse

    fake = Host()
    monkeypatch.setattr(sse, "_broadcast_runner", fake)
    return fake


@pytest.fixture(autouse=True)
def _no_watcher_outlives_its_test():
    """A chief a test leaves open has a watcher waiting; close it while this test's DB and
    sessions folder are still patched in, so it cannot wake up in a later test."""
    yield
    from pathly_orchestrator.supervisor.chief_session import close_chief

    prefix = "chief-watch-"
    for thread in threading.enumerate():
        if thread.name.startswith(prefix):
            close_chief(thread.name[len(prefix) :], "test over")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and any(
        t.name.startswith(prefix) for t in threading.enumerate()
    ):
        time.sleep(0.01)


def fragment_text() -> str:
    """The ``chief-connect`` fragment as the file holds it."""
    return FRAGMENT_PATH.read_text(encoding="utf-8")
