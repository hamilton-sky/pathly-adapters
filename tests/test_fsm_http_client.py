import json
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


def test_next_action_auto_starts_server_and_posts_json(monkeypatch):
    calls = []
    health_attempts = {"count": 0}

    def fake_popen(cmd, **kwargs):
        calls.append(("popen", cmd, kwargs))

        class Proc:
            pass

        return Proc()

    def fake_sleep(seconds):
        calls.append(("sleep", seconds))

    def fake_urlopen(request, timeout=0):
        calls.append((request.full_url, request.get_method(), timeout))
        if request.full_url.endswith("/health"):
            health_attempts["count"] += 1
            if health_attempts["count"] == 1:
                raise URLError("down")
            return _Response('{"status":"ok"}')

        payload = json.loads(request.data.decode("utf-8"))
        assert payload == {
            "flow": "team",
            "topic": "demo",
            "project_root": "C:/work/project",
        }
        return _Response('{"current_state":"BUILDING","menu":{"state":"BUILDING"}}')

    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", fake_popen)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.time.sleep", fake_sleep)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)

    result = client.next_action(
        {"flow": "team", "topic": "demo", "project_root": "C:/work/project"}
    )

    assert result["current_state"] == "BUILDING"
    assert any(call[0] == "popen" for call in calls)
    network_calls = [call for call in calls if isinstance(call[0], str) and call[0].startswith("http")]
    assert network_calls[0][0].endswith("/health")
    assert network_calls[-1][0].endswith("/next_action")
    popen_call = next(call for call in calls if call[0] == "popen")
    assert popen_call[1] == [sys.executable, "-m", "pathly_orchestrator.http_server"]


def test_record_activity_cli_prints_raw_json(monkeypatch, capsys):
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

    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.urlopen", fake_urlopen)
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.subprocess.Popen", lambda *args, **kwargs: object())
    monkeypatch.setattr("pathly_orchestrator.fsm_http_client.time.sleep", lambda _: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "pathly-fsm-call",
            "record-activity",
            "--agent",
            "builder",
            "--feature",
            "demo",
            "--summary",
            "builder conv 1 DONE",
            "--conversation",
            "1",
            "--input-tokens",
            "12",
            "--output-tokens",
            "3",
        ],
    )

    with pytest.raises(SystemExit) as exc:
        client.main()

    assert exc.value.code == 0
    assert calls[0][0].endswith("/health")
    assert calls[-1][0].endswith("/record_activity")
    assert capsys.readouterr().out.strip() == '{"status":"recorded"}'
