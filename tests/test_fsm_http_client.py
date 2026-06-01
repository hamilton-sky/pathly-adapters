import json
import os
import sys
from urllib.error import URLError

import pytest

from pathly_orchestrator import fsm_http_client as client


class _Response:
    def __init__(self, body: str):
        self._body = body.encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeProc:
    pid = 12345


# ── ensure_server_running + auto-start integration ───────────────────────────

def test_next_action_auto_starts_server_and_posts_json(monkeypatch, tmp_path):
    """Server down on first check; up on first poll iteration; request succeeds."""
    calls = []
    health_count = {"n": 0}

    def fake_popen(cmd, **kwargs):
        calls.append(("popen", cmd, kwargs))
        return _FakeProc()

    def fake_urlopen(request, timeout=0):
        calls.append((request.full_url, request.get_method(), timeout))
        if request.full_url.endswith("/health"):
            health_count["n"] += 1
            if health_count["n"] == 1:
                raise URLError("down")
            return _Response('{"status":"ok"}')
        payload = json.loads(request.data.decode("utf-8"))
        assert payload == {"flow": "team", "topic": "demo", "project_root": "C:/work/project"}
        return _Response('{"current_state":"BUILDING","menu":{"state":"BUILDING"}}')

    pid_file = tmp_path / "fsm.pid"
    monkeypatch.setattr(client, "_pid_file", lambda: pid_file)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", fake_popen)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.time.sleep", lambda s: calls.append(("sleep", s)))
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)

    result = client.next_action(
        {"flow": "team", "topic": "demo", "project_root": "C:/work/project"}
    )

    assert result["current_state"] == "BUILDING"
    assert any(c[0] == "popen" for c in calls)
    net = [c for c in calls if isinstance(c[0], str) and c[0].startswith("http")]
    assert net[0][0].endswith("/health")
    assert net[-1][0].endswith("/next_action")
    popen_call = next(c for c in calls if c[0] == "popen")
    assert popen_call[1] == [sys.executable, "-m", "pathly_orchestrator.http_server"]
    assert pid_file.read_text() == str(_FakeProc.pid)


def test_poll_exits_early_on_first_healthy_response(monkeypatch, tmp_path):
    """Poll loop returns immediately after first successful /health response."""
    sleep_calls = []
    health_count = {"n": 0}

    def fake_urlopen(request, timeout=0):
        if request.full_url.endswith("/health"):
            health_count["n"] += 1
            if health_count["n"] == 1:
                raise URLError("down")  # initial check in ensure_server_running
            return _Response('{"status":"ok"}')  # first poll attempt passes
        return _Response("{}")

    monkeypatch.setattr(client, "_pid_file", lambda: tmp_path / "fsm.pid")
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", lambda *a, **k: _FakeProc())
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.time.sleep", lambda s: sleep_calls.append(s))
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)

    client.ensure_server_running()

    # Poll loop checks health before sleeping, so exiting on the first iteration means no sleep.
    assert sleep_calls == [], "no sleep when first poll attempt succeeds"
    assert health_count["n"] == 2  # initial check + 1 poll iteration


def test_poll_exhausted_raises_runtime_error(monkeypatch, tmp_path):
    """All 30 poll attempts fail → RuntimeError with the expected message."""
    def fake_urlopen(request, timeout=0):
        raise URLError("down")

    monkeypatch.setattr(client, "_pid_file", lambda: tmp_path / "fsm.pid")
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", lambda *a, **k: _FakeProc())
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.time.sleep", lambda _: None)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="did not start within 7.5 s"):
        client.ensure_server_running()


# ── _start_server PID file behaviour ─────────────────────────────────────────

def test_pid_file_live_process_skips_spawn(monkeypatch, tmp_path):
    """Existing PID file + healthy server → no Popen call."""
    pid_file = tmp_path / "fsm.pid"
    pid_file.write_text("12345")
    spawn_calls = []

    def fake_urlopen(request, timeout=0):
        if request.full_url.endswith("/health"):
            return _Response('{"status":"ok"}')
        return _Response("{}")

    monkeypatch.setattr(client, "_pid_file", lambda: pid_file)
    monkeypatch.setattr(
        "pathly_orchestrator.fsm_http_client.subprocess.Popen",
        lambda *a, **k: spawn_calls.append(True) or _FakeProc(),
    )
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)

    client._start_server()

    assert spawn_calls == [], "Popen must not fire when server is already up"


def test_pid_file_stale_process_spawns_fresh(monkeypatch, tmp_path):
    """Stale PID file (health fails) → file deleted, fresh Popen call."""
    pid_file = tmp_path / "fsm.pid"
    pid_file.write_text("99999")
    spawn_calls = []
    health_count = {"n": 0}

    def fake_urlopen(request, timeout=0):
        if request.full_url.endswith("/health"):
            health_count["n"] += 1
            if health_count["n"] == 1:
                raise URLError("stale")
            return _Response('{"status":"ok"}')
        return _Response("{}")

    monkeypatch.setattr(client, "_pid_file", lambda: pid_file)
    monkeypatch.setattr(
        "pathly_orchestrator.fsm_http_client.subprocess.Popen",
        lambda *a, **k: spawn_calls.append(True) or _FakeProc(),
    )
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)

    client._start_server()

    assert len(spawn_calls) == 1
    assert pid_file.read_text() == str(_FakeProc.pid)


# ── Platform-specific spawn flags ────────────────────────────────────────────

@pytest.mark.skipif(os.name == "nt", reason="POSIX-only")
def test_posix_spawn_uses_start_new_session(monkeypatch, tmp_path):
    """On POSIX, Popen is called with start_new_session=True, no creationflags."""
    spawn_kwargs: dict = {}

    def fake_popen(cmd, **kwargs):
        spawn_kwargs.update(kwargs)
        return _FakeProc()

    def always_down(request, timeout=0):
        raise URLError("down")

    monkeypatch.setattr(client, "_pid_file", lambda: tmp_path / "fsm.pid")
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", fake_popen)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", always_down)

    client._start_server()  # will spawn; health inside _start_server fails, that's ok

    assert spawn_kwargs.get("start_new_session") is True
    assert "creationflags" not in spawn_kwargs


@pytest.mark.skipif(os.name != "nt", reason="Windows-only")
def test_windows_spawn_uses_detached_process_flags(monkeypatch, tmp_path):
    """On Windows, Popen is called with CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS."""
    import subprocess as _sp

    spawn_kwargs: dict = {}

    def fake_popen(cmd, **kwargs):
        spawn_kwargs.update(kwargs)
        return _FakeProc()

    def always_down(request, timeout=0):
        raise URLError("down")

    monkeypatch.setattr(client, "_pid_file", lambda: tmp_path / "fsm.pid")
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", fake_popen)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", always_down)

    client._start_server()

    expected = _sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS
    assert spawn_kwargs.get("creationflags") == expected
    assert "start_new_session" not in spawn_kwargs


# ── CLI record-activity ───────────────────────────────────────────────────────

def test_record_activity_cli_prints_raw_json(monkeypatch, capsys, tmp_path):
    calls = []

    def fake_urlopen(request, timeout=0):
        calls.append((request.full_url, request.get_method()))
        if request.full_url.endswith("/health"):
            return _Response('{"status":"ok"}')
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["agent"] == "builder"
        assert payload["feature"] == "demo"
        assert payload["summary"] == "builder conv 1 DONE"
        assert payload["input_tokens"] == 12
        assert payload["output_tokens"] == 3
        return _Response('{"status":"recorded"}')

    monkeypatch.setattr(client, "_pid_file", lambda: tmp_path / "fsm.pid")
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", lambda *a, **k: _FakeProc())
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.time.sleep", lambda _: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pathly-fsm-call",
            "record-activity",
            "--agent", "builder",
            "--feature", "demo",
            "--summary", "builder conv 1 DONE",
            "--conversation", "1",
            "--input-tokens", "12",
            "--output-tokens", "3",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        client.main()

    assert exc.value.code == 0
    assert calls[0][0].endswith("/health")
    assert calls[-1][0].endswith("/record_activity")
    assert capsys.readouterr().out.strip() == '{"status":"recorded"}'
