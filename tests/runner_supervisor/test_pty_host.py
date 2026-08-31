"""Tests for the headless spawn host (``pathly-pty-host``).

The host exists to remove Studio from the critical path of a run, so the tests spawn REAL
subprocesses and — for the end-to-end case — talk to a REAL Flask server over a REAL
socket. Mocking the spawn or the transport would test the one thing that was never in
doubt while skipping the thing that was.
"""

from __future__ import annotations

import sys
import threading
import time

import pytest

from pathly_orchestrator.pty_host import SpawnHost
from pathly_orchestrator.pty_host import client as host_client
from pathly_orchestrator.pty_host import host as host_mod
from pathly_orchestrator.pty_host.process import OutputTail, SpawnedProcess

# ── Helpers ───────────────────────────────────────────────────────────────────


def _spawn_event(code: str, **overrides) -> dict:
    """A TERMINAL_SPAWN whose argv runs `code` in this interpreter."""
    event = {
        "type": "TERMINAL_SPAWN",
        "topic": "demo",
        "run_id": "run-abc123",
        "tab_id": "runner-abc123",
        "label": "claude — BUILDING",
        "adapter": "claude",
        "argv": [sys.executable, "-c", code],
        "cwd": ".",
        "interactive": False,
    }
    event.update(overrides)
    return event


class _Recorder:
    """Stands in for the two server callbacks and records what the host reported."""

    def __init__(self) -> None:
        self.started: list[dict] = []
        self.results: list[dict] = []
        self.result_seen = threading.Event()

    def install(self, monkeypatch) -> None:
        def _started(**kwargs):
            self.started.append(kwargs)
            return True

        def _result(**kwargs):
            self.results.append(kwargs)
            self.result_seen.set()
            return True

        for module in (host_client, host_mod.client):
            monkeypatch.setattr(module, "post_started", _started, raising=False)
            monkeypatch.setattr(module, "post_result", _result, raising=False)

    def wait(self, timeout: float = 30.0) -> dict:
        assert self.result_seen.wait(timeout), "host never reported a result"
        return self.results[-1]


def _drive(host: SpawnHost, *events: dict) -> None:
    """Feed events through the host's dispatcher as the SSE loop would."""
    for event in events:
        host._dispatch(event)


# ── OutputTail ────────────────────────────────────────────────────────────────


def test_output_tail_keeps_everything_under_the_cap():
    tail = OutputTail(max_bytes=100)
    tail.append("hello ")
    tail.append("world")
    assert tail.text() == "hello world"


def test_output_tail_drops_the_oldest_chunks_over_the_cap():
    tail = OutputTail(max_bytes=10)
    for chunk in ("aaaaa", "bbbbb", "ccccc"):
        tail.append(chunk)

    text = tail.text()
    assert text.endswith("ccccc")  # the tail is what the result parser needs
    assert "aaaaa" not in text
    assert len(text) <= 10


# ── SpawnedProcess ────────────────────────────────────────────────────────────


def test_spawned_process_captures_output_and_exit_code(tmp_path):
    proc = SpawnedProcess(
        [
            sys.executable,
            "-c",
            "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(4)",
        ],
        str(tmp_path),
        {"PATH": "/usr/bin:/bin"},
    )
    exit_code = proc.wait()

    assert exit_code == 4
    text = proc.tail.text()
    assert "out" in text
    assert "err" in text  # stderr is merged, so the failure reason survives


def test_spawned_process_gets_devnull_stdin(tmp_path):
    """codex headless stalls on an inherited stdin; the host must close it."""
    proc = SpawnedProcess(
        [sys.executable, "-c", "import sys; print(repr(sys.stdin.read()))"],
        str(tmp_path),
        {"PATH": "/usr/bin:/bin"},
    )
    assert proc.wait() == 0
    assert "''" in proc.tail.text()


def test_terminate_kills_the_process(tmp_path):
    proc = SpawnedProcess(
        [sys.executable, "-c", "import time; time.sleep(120)"],
        str(tmp_path),
        {"PATH": "/usr/bin:/bin"},
    )
    proc.terminate()

    assert proc.wait() != 0
    assert proc.killed_by_host is True


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX process groups")
def test_terminate_reaches_a_grandchild(tmp_path):
    """Killing only the direct child is what leaves orphaned CLI processes behind."""
    marker = tmp_path / "grandchild-alive"
    code = (
        "import subprocess, sys, time; "
        f"subprocess.Popen([sys.executable, '-c', "
        f"\"import time, pathlib; [ (pathlib.Path(r'{marker}').touch(), time.sleep(0.2)) for _ in range(200) ]\"]); "
        "time.sleep(120)"
    )
    proc = SpawnedProcess(
        [sys.executable, "-c", code], str(tmp_path), dict(**{"PATH": "/usr/bin:/bin"})
    )
    for _ in range(100):  # let the grandchild come up
        if marker.exists():
            break
        time.sleep(0.05)
    assert marker.exists(), "grandchild never started"

    proc.terminate()
    proc.wait()
    marker.unlink()
    time.sleep(0.6)  # longer than the grandchild's touch interval

    assert not marker.exists(), "grandchild outlived the kill — orphaned process"


# ── Host dispatch ─────────────────────────────────────────────────────────────


def test_host_spawns_and_reports_the_result(monkeypatch, tmp_path):
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("print('hello from the agent')", cwd=str(tmp_path)))
    result = rec.wait()

    assert rec.started and rec.started[0]["run_id"] == "run-abc123"
    assert result["exit_code"] == 0
    assert "hello from the agent" in result["stdout_tail"]
    assert result["run_id"] == "run-abc123"
    assert result["topic"] == "demo"
    assert result["user_initiated"] is False


def test_host_relays_the_spawn_time_adapter(monkeypatch, tmp_path):
    """The server parses stdout with THIS adapter; guessing it later reads $0 for codex."""
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("pass", adapter="CODEX", cwd=str(tmp_path)))

    assert rec.wait()["adapter"] == "codex"


def test_host_relays_a_nonzero_exit(monkeypatch, tmp_path):
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("raise SystemExit(3)", cwd=str(tmp_path)))

    assert rec.wait()["exit_code"] == 3


def test_host_ignores_a_redelivered_spawn(monkeypatch, tmp_path):
    """A reconnect can redeliver an event — the same tab must never spawn twice."""
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()
    event = _spawn_event("print('once')", cwd=str(tmp_path))

    _drive(host, event, event)
    rec.wait()
    time.sleep(0.5)

    assert len(rec.results) == 1


def test_host_refuses_an_interactive_stage_instead_of_hanging(monkeypatch, tmp_path):
    """No terminal, no human — fail in a second rather than time out in 30 minutes."""
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("pass", interactive=True, cwd=str(tmp_path)))
    result = rec.wait(timeout=5)

    assert result["exit_code"] == 1
    assert "INTERACTIVE" in result["stdout_tail"]
    assert not rec.started  # never claimed to have spawned


def test_host_reports_an_unspawnable_command(monkeypatch, tmp_path):
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(
        host,
        _spawn_event("pass", argv=["pathly-no-such-binary-xyz"], cwd=str(tmp_path)),
    )
    result = rec.wait(timeout=10)

    assert result["exit_code"] == 1
    assert "could not spawn" in result["stdout_tail"]


def test_host_kills_on_terminal_kill(monkeypatch, tmp_path):
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("import time; time.sleep(120)", cwd=str(tmp_path)))
    for _ in range(200):  # wait until the child is actually registered
        if rec.started:
            break
        time.sleep(0.05)
    assert rec.started, "spawn never started"

    _drive(host, {"type": "TERMINAL_KILL", "tab_id": "runner-abc123"})
    result = rec.wait(timeout=20)

    assert result["exit_code"] != 0
    assert result["user_initiated"] is True  # a kill is not a crash


def test_terminal_signal_term_also_kills(monkeypatch, tmp_path):
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("import time; time.sleep(120)", cwd=str(tmp_path)))
    for _ in range(200):
        if rec.started:
            break
        time.sleep(0.05)

    _drive(
        host,
        {"type": "TERMINAL_SIGNAL", "signal": "term", "tab_id": "runner-abc123"},
    )

    assert rec.wait(timeout=20)["user_initiated"] is True


def test_host_marks_the_child_env(monkeypatch, tmp_path):
    """PATHLY_GATE_BILLED keeps the interactive stop hook from double-billing this run."""
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(
        host,
        _spawn_event(
            "import os; print(os.environ['PATHLY_GATE_BILLED'], os.environ['PATHLY_PROJECT_ROOT'])",
            cwd=str(tmp_path),
        ),
    )
    out = rec.wait()["stdout_tail"]

    assert "1" in out
    assert str(tmp_path) in out


def test_stop_kills_running_children(monkeypatch, tmp_path):
    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()

    _drive(host, _spawn_event("import time; time.sleep(120)", cwd=str(tmp_path)))
    for _ in range(200):
        if rec.started:
            break
        time.sleep(0.05)

    host.stop()

    assert rec.wait(timeout=20)["exit_code"] != 0


def test_claim_memory_evicts_in_lockstep(monkeypatch, tmp_path):
    """A host that drains for weeks must not keep one tab_id per stage forever.

    The deque bounds itself; the lookup SET beside it does not, so the eviction has to
    prune both. Driving real spawns through a deliberately tiny cap proves it does.
    """
    from collections import deque

    rec = _Recorder()
    rec.install(monkeypatch)
    host = SpawnHost()
    host._claimed = deque(maxlen=3)

    for i in range(6):
        _drive(host, _spawn_event("pass", tab_id=f"tab-{i}", cwd=str(tmp_path)))

    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and len(rec.results) < 6:
        time.sleep(0.05)

    assert len(rec.results) == 6, "every distinct tab should have spawned"
    assert len(host._claimed) == 3
    assert len(host._claimed_index) == 3, "the lookup set leaked past the cap"
    assert host._claimed_index == {"tab-3", "tab-4", "tab-5"}
