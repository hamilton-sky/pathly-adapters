"""chief-agent 20, B7: a second server started on a busy port leaves the first server's chief open.

``main()`` closes every chief session of the shared database before it serves. A second
``pathly-fsm`` started by mistake on the port the first one serves therefore revoked the running
server's chief (token revoked, folder removed, tab left dead) and only then died with "address
already in use". ``main()`` now first asks whether something already answers on the host and port
it is about to serve (a TCP connect to 127.0.0.1 when the host is a wildcard address; any error
means nothing answers). If something does, it leaves the sessions alone, logs one line and goes on
to fail in ``app.run`` as before.

``main()`` resets the root logger and the middleware globals and starts threads, so it runs in a
process of its own with its own home, with Flask's ``run`` replaced by a recorder.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from contextlib import closing, contextmanager
from pathlib import Path

import pytest
from _paths import SRC
from chief_gate_support import _chief, project

SCRIPT = """
import importlib, json
app_module = importlib.import_module("pathly_orchestrator.http_server.app")
import pathly_orchestrator.runner.embeddings as embeddings
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief as queries
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, resolve_run_token

embeddings.warm = lambda: None
served = []
app_module.app.run = lambda *a, **k: served.append((a, k))

conn = get_db()
queries.create_session(
    conn, run_id="chief-0123456789ab", project_root="/p", preset="status", tier="status",
    engine="claude", tab_id="chief-0123456789ab", cli_session_id=None,
    hook_secret_hash=None, settings_dir=None,
)
token = mint_run_token(conn, "chief-0123456789ab", "chief", None, "/p", "project", "/p")
app_module.main()
print(json.dumps({
    "served": [{"host": k.get("host"), "port": k.get("port")} for _, k in served],
    "open": queries.open_session_for_project(conn, "/p") is not None,
    "token_live": resolve_run_token(conn, token) is not None,
}))
"""


@contextmanager
def _listening():
    """A socket that accepts connections (the kernel completes them) on a free port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(5)
        yield sock.getsockname()[1]
    finally:
        sock.close()


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_main(tmp_path: Path, port: int) -> tuple[dict, str]:
    home = tmp_path / "main-home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": str(SRC),
        "PATHLY_FSM_HTTP_PORT": str(port),
    }
    env.pop("PATHLY_FSM_HTTP_HOST", None)
    done = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1]), done.stderr


# --- main(), as a process ------------------------------------------------------------------------


def test_main_leaves_a_chief_open_when_something_already_answers_on_its_port(tmp_path):
    with _listening() as port:
        report, stderr = _run_main(tmp_path, port)

    assert report["open"] is True
    assert report["token_live"] is True
    assert report["served"] == [{"host": "127.0.0.1", "port": port}]
    notes = [line for line in stderr.splitlines() if "already answers" in line]
    assert len(notes) == 1, stderr
    assert f"127.0.0.1:{port}" in notes[0]


def test_main_closes_the_sessions_when_nothing_answers_on_its_port(tmp_path):
    port = _free_port()

    report, stderr = _run_main(tmp_path, port)

    assert report["open"] is False
    assert report["token_live"] is False
    assert report["served"] == [{"host": "127.0.0.1", "port": port}]
    assert "already answers" not in stderr


# --- the probe -----------------------------------------------------------------------------------


def _answers(host: str, port: int) -> bool:
    from pathly_orchestrator.supervisor.chief_session import something_answers

    return something_answers(host, port)


def test_the_probe_sees_a_listening_socket_and_not_a_closed_port():
    with _listening() as port:
        assert _answers("127.0.0.1", port) is True
    assert _answers("127.0.0.1", port) is False


@pytest.mark.parametrize("wildcard", ["0.0.0.0", "", "::", "::0", "0:0:0:0:0:0:0:0"])
def test_a_wildcard_host_is_probed_on_127_0_0_1(wildcard):
    with _listening() as port:
        assert _answers(wildcard, port) is True
    assert _answers(wildcard, port) is False


@pytest.mark.parametrize(
    "host, port",
    [
        ("no-such-host.invalid", 1),
        ("127.0.0.1", 0),
        ("127.0.0.1", 70000),
        ("not a host", 1),
        (object(), 1),
    ],
    ids=["unresolvable", "port-0", "port-too-large", "not-a-host", "not-a-string"],
)
def test_any_error_counts_as_nothing_answers(host, port):
    assert _answers(host, port) is False


# --- the cleanup without arguments ---------------------------------------------------------------


def test_the_cleanup_with_no_arguments_still_closes_every_open_session(project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import resolve_run_token
    from pathly_orchestrator.supervisor.chief_session import chief_startup_cleanup

    chief = _chief("status", project)

    closed = chief_startup_cleanup()

    assert closed == [chief.run_id]
    assert resolve_run_token(get_db(), chief.token) is None
