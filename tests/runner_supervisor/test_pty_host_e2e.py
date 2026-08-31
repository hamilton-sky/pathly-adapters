"""End-to-end: a supervisor spawn wait satisfied WITHOUT Studio.

This is the test the feature exists for. ``supervisor/terminal.py`` broadcasts
``TERMINAL_SPAWN`` and then blocks on ``TerminalRun.wait_started(30)`` and
``wait_pty_result(...)``; until now only Studio's Electron main process could release
those, so a run could not drain on a server or in CI.

Everything below is real: a real Flask server on a real port, a real SSE connection, a
real subprocess, and the real ``TerminalRun`` the supervisor waits on. Only the CLI itself
is substituted (a python one-liner instead of `claude -p`), because the contract under test
is the host↔server handshake, not the agent.
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from pathly_orchestrator.pty_host import SpawnHost

pytest.importorskip("werkzeug")


@pytest.fixture(scope="module")
def live_server():
    """The real FSM app on an ephemeral port, threaded so SSE cannot block a POST.

    Module-scoped on purpose. An open SSE generator only notices its client is gone at the
    next 25s keepalive, so tearing the server down costs ~25s — worth paying once for the
    file, not once per test. Each test still gets a fresh host and a fresh subscriber.
    """
    from werkzeug.serving import make_server

    from pathly_orchestrator.http_server import middleware as _middleware
    from pathly_orchestrator.http_server.app import app

    _middleware.configure(cors_origin="*", api_secret="")
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_port
    finally:
        server.shutdown()
        thread.join(timeout=30)


@pytest.fixture
def spawn_host(live_server):
    """A running host pointed at the live server, connected before the test proceeds."""
    from pathly_orchestrator.http_server import sse as _sse

    # Drop any subscriber left over from a previous test: the spawn channel fans out to
    # every registered queue, so a stale one absorbs the broadcast while THIS host is
    # still connecting, and the run then waits out its full 30s spawn timeout.
    with _sse._spawn_lock:
        _sse._spawn_clients.clear()

    host = SpawnHost(host="127.0.0.1", port=live_server)
    thread = threading.Thread(target=host.run, daemon=True, name="pty-host-test")
    thread.start()

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not _sse._spawn_clients:
        time.sleep(0.05)
    assert _sse._spawn_clients, "host never subscribed to /events/spawn"

    try:
        yield host
    finally:
        host.stop()
        thread.join(timeout=10)


def _broadcast(topic: str, payload: dict) -> None:
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    _broadcast_runner(topic, payload)


def _spawn_payload(run_id: str, code: str, cwd: str, **overrides) -> dict:
    payload = {
        "type": "TERMINAL_SPAWN",
        "topic": "e2e-topic",
        "run_id": run_id,
        "tab_id": f"runner-{run_id[-10:]}",
        "label": "claude — BUILDING",
        "adapter": "claude",
        "argv": [sys.executable, "-c", code],
        "cwd": cwd,
        "interactive": False,
        "category": "flow",
    }
    payload.update(overrides)
    return payload


def test_host_releases_the_supervisor_spawn_and_result_waits(
    spawn_host, tmp_path, live_server
):
    """The whole point: both supervisor waits complete with no Studio in the loop."""
    from pathly_orchestrator import supervisor as _sup

    run_id = "e2e-run-0001"
    run = _sup.create_run(run_id)
    try:
        _broadcast(
            "e2e-topic",
            _spawn_payload(run_id, "print('agent output')", str(tmp_path)),
        )

        # This is the wait that used to raise "terminal_spawn_timeout: Studio did not
        # spawn PTY ... within 30s" with no desktop app running.
        assert run.wait_started(timeout=30), "no host answered TERMINAL_SPAWN"
        assert run.wait_pty_result(timeout=60), "no host reported a result"

        assert run.pty_result is not None
        assert run.pty_result["exit_code"] == 0
        assert run.pty_result["wall_seconds"] >= 0
    finally:
        _sup.drop_run(run_id)


def test_a_failing_agent_reports_its_exit_code_end_to_end(
    spawn_host, tmp_path, live_server
):
    from pathly_orchestrator import supervisor as _sup

    run_id = "e2e-run-0002"
    run = _sup.create_run(run_id)
    try:
        _broadcast(
            "e2e-topic",
            _spawn_payload(
                run_id,
                "import sys; print('boom', file=sys.stderr); raise SystemExit(2)",
                str(tmp_path),
            ),
        )

        assert run.wait_started(timeout=30)
        assert run.wait_pty_result(timeout=60)
        assert run.pty_result["exit_code"] == 2
    finally:
        _sup.drop_run(run_id)


def test_terminal_kill_over_the_wire_stops_a_running_agent(
    spawn_host, tmp_path, live_server
):
    """An abort must actually reach the CLI, not just stop the supervisor waiting."""
    from pathly_orchestrator import supervisor as _sup

    run_id = "e2e-run-0003"
    tab_id = f"runner-{run_id[-10:]}"
    run = _sup.create_run(run_id)
    try:
        _broadcast(
            "e2e-topic",
            _spawn_payload(run_id, "import time; time.sleep(120)", str(tmp_path)),
        )
        assert run.wait_started(timeout=30)

        _broadcast(
            "e2e-topic",
            {"type": "TERMINAL_KILL", "tab_id": tab_id, "run_id": run_id},
        )

        assert run.wait_pty_result(timeout=30), "kill did not produce a result"
        assert run.pty_result["exit_code"] != 0
        assert run.pty_result["user_initiated"] is True
    finally:
        _sup.drop_run(run_id)


def test_two_runs_drain_concurrently(spawn_host, tmp_path, live_server):
    """A goal DAG spawns several stages; the host must not serialize them into a queue of one."""
    from pathly_orchestrator import supervisor as _sup

    run_ids = ["e2e-run-0010", "e2e-run-0011"]
    runs = {rid: _sup.create_run(rid) for rid in run_ids}
    try:
        started = time.monotonic()
        for rid in run_ids:
            _broadcast(
                "e2e-topic",
                _spawn_payload(rid, "import time; time.sleep(2)", str(tmp_path)),
            )

        for rid in run_ids:
            assert runs[rid].wait_pty_result(timeout=60), f"{rid} never reported"
            assert runs[rid].pty_result["exit_code"] == 0

        # Serial execution would take >= 4s; concurrent stays near 2s.
        assert time.monotonic() - started < 4.0
    finally:
        for rid in run_ids:
            _sup.drop_run(rid)


def test_shutdown_is_prompt_on_an_idle_stream(live_server):
    """Ctrl-C must not wait for the server's next keepalive.

    An idle SSE reader blocks inside BufferedReader.readline(), holding the buffer lock.
    Closing the response needs that same lock, so a close-based stop only returns at the
    next 25s keepalive — a quarter-minute hang on every shutdown. The host shuts the
    socket down instead.
    """
    from pathly_orchestrator.http_server import sse as _sse

    with _sse._spawn_lock:
        _sse._spawn_clients.clear()

    host = SpawnHost(host="127.0.0.1", port=live_server)
    thread = threading.Thread(target=host.run, daemon=True, name="pty-host-idle")
    thread.start()

    deadline = time.monotonic() + 20
    while time.monotonic() < deadline and not _sse._spawn_clients:
        time.sleep(0.05)
    assert _sse._spawn_clients, "host never subscribed"
    time.sleep(0.3)  # settle into the blocking read

    started = time.monotonic()
    host.stop()
    thread.join(timeout=10)
    elapsed = time.monotonic() - started

    assert not thread.is_alive(), "host thread outlived stop()"
    assert elapsed < 5.0, f"stop() took {elapsed:.1f}s — blocked until the keepalive"
