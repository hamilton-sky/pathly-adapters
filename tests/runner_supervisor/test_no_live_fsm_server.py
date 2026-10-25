"""The test process never reaches the developer's FSM server, nor starts one.

When Studio runs, a live FSM server listens on 127.0.0.1:8765, and ``fsm_http_client`` starts
``python -m pathly_orchestrator.http_server`` detached when nothing answers. A test that left a
real supervisor loop running wrote a fake goal run into that server, or left a server of its own
running after pytest. ``tests/conftest.py`` refuses both (``_no_live_fsm_server``); these tests
pin it, whether or not a server is running on this machine.
"""

from __future__ import annotations

import socket
import subprocess
import sys

import pytest
from conftest import FSM_SERVER_MODULE, LIVE_FSM_PORT


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_a_connection_to_the_live_fsm_port_is_refused(host):
    with pytest.raises(ConnectionRefusedError, match="tests do not connect"):
        socket.create_connection((host, LIVE_FSM_PORT), timeout=2)


def test_a_connection_to_any_other_port_still_works():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=2):
            pass


@pytest.mark.parametrize(
    "argv",
    [
        [sys.executable, "-m", FSM_SERVER_MODULE],
        ["pathly-fsm-http", "--port", "8765"],
    ],
    ids=["module", "console-script"],
)
def test_starting_the_fsm_server_is_refused(argv):
    with pytest.raises(PermissionError, match="do not start the FSM server"):
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def test_another_python_child_still_starts():
    done = subprocess.run(
        [sys.executable, "-c", "print('ok')"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert done.stdout.strip() == "ok"


def test_the_fsm_client_falls_back_in_process_without_starting_a_server(
    tmp_path, monkeypatch
):
    """What a supervisor loop in a test gets: the in-process FSM, not a server."""
    from pathly_orchestrator import fsm_http_client

    calls = []
    monkeypatch.setattr(
        fsm_http_client,
        "_inprocess",
        lambda name, payload: calls.append(name) or {"ok": 1},
    )
    monkeypatch.setattr(fsm_http_client, "_pid_file", lambda: tmp_path / "fsm.pid")

    answer = fsm_http_client.next_action(
        {"flow": "team", "topic": "demo", "project_root": str(tmp_path)}
    )

    assert answer == {"ok": 1}
    assert calls == ["next_action"]
