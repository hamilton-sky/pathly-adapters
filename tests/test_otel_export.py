import http.client
import urllib.error
from unittest import mock
from pathly_orchestrator.otel_export import (
    _build_span_payload,
    _do_export,
    export_span_async,
)

MINIMAL_EVENT = {
    "type": "AGENT_DONE",
    "agent": "builder",
    "feature": "my-feature",
    "ts": "2026-01-01T00:00:00Z",
    "result": "pass",
    "tokens_in": 100,
    "tokens_out": 50,
    "cost_usd": 0.001,
    "wall_seconds": 30,
    "model": "claude-sonnet-4-6",
    "conversation": 1,
    "summary": "Built the thing",
    "trace_id": "a" * 32,
    "span_id": "b" * 16,
}


def test_no_op_when_env_unset(monkeypatch):
    monkeypatch.delenv("PATHLY_OTEL_ENDPOINT", raising=False)
    with mock.patch("threading.Thread") as mock_thread:
        export_span_async(MINIMAL_EVENT)
    assert mock_thread.call_count == 0


def test_span_payload_structure():
    payload = _build_span_payload(MINIMAL_EVENT)
    assert "resourceSpans" in payload
    span = payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["name"] == "invoke_agent builder"
    assert span["traceId"] == "a" * 32
    assert span["spanId"] == "b" * 16
    attr_keys = {a["key"] for a in span["attributes"]}
    assert "gen_ai.agent.name" in attr_keys
    assert "pathly.cost_usd" in attr_keys


def test_span_status_ok():
    for result in ("pass", "done", "DONE"):
        ev = {**MINIMAL_EVENT, "result": result}
        span = _build_span_payload(ev)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["status"]["code"] == 1, f"expected OK for result={result}"


def test_span_status_error():
    for result in ("fail", "error"):
        ev = {**MINIMAL_EVENT, "result": result}
        span = _build_span_payload(ev)["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
        assert span["status"]["code"] == 2, f"expected ERROR for result={result}"


def test_do_export_swallows_network_error(monkeypatch, caplog):
    monkeypatch.setattr(
        "urllib.request.urlopen", mock.Mock(side_effect=OSError("refused"))
    )
    import logging

    with caplog.at_level(logging.WARNING):
        _do_export(MINIMAL_EVENT, "http://localhost:4318")
    assert "otel export failed" in caplog.text


def test_do_export_swallows_http_error(monkeypatch, caplog):
    http_err = urllib.error.HTTPError(
        "http://localhost:4318/v1/traces",
        503,
        "Service Unavailable",
        http.client.HTTPMessage(),
        None,
    )
    monkeypatch.setattr("urllib.request.urlopen", mock.Mock(side_effect=http_err))
    import logging

    with caplog.at_level(logging.WARNING):
        _do_export(MINIMAL_EVENT, "http://localhost:4318")
    assert "otel export failed" in caplog.text


def test_log_not_posted_when_no_summary(monkeypatch):
    mock_resp = mock.MagicMock()
    mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
    mock_resp.__exit__ = mock.Mock(return_value=False)
    mock_resp.status = 200
    mock_urlopen = mock.Mock(return_value=mock_resp)
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    ev = {**MINIMAL_EVENT, "summary": ""}
    _do_export(ev, "http://localhost:4318")
    assert mock_urlopen.call_count == 1


def test_log_posted_when_summary_present(monkeypatch):
    mock_resp = mock.MagicMock()
    mock_resp.__enter__ = mock.Mock(return_value=mock_resp)
    mock_resp.__exit__ = mock.Mock(return_value=False)
    mock_resp.status = 200
    mock_urlopen = mock.Mock(return_value=mock_resp)
    monkeypatch.setattr("urllib.request.urlopen", mock_urlopen)
    ev = {**MINIMAL_EVENT, "summary": "did things"}
    _do_export(ev, "http://localhost:4318")
    assert mock_urlopen.call_count == 2


def test_record_activity_unaffected_by_export_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("PATHLY_OTEL_ENDPOINT", "http://127.0.0.1:1")
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    feature_dir = tmp_path / "pathly" / "plans" / "test"
    feature_dir.mkdir(parents=True)
    with app.test_client() as c:
        r = c.post(
            "/record_activity",
            json={
                "agent": "builder",
                "feature": "test",
                "project_root": str(tmp_path),
                "summary": "done",
                "input_tokens": 10,
                "output_tokens": 5,
            },
        )
    assert r.status_code == 200
