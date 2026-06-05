"""Integration tests for the HTTP server endpoints."""
from __future__ import annotations

import json
import threading
from unittest.mock import patch

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask test client with isolated tmp dirs."""
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.http_server import app, _rate_counters
    _rate_counters.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def test_health_returns_ok(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["status"] == "ok"


def test_rate_limit_blocks_after_limit(client, monkeypatch):
    from pathly_orchestrator import http_server
    monkeypatch.setenv("PATHLY_FF_RATE_LIMITING", "true")
    orig = http_server._RATE_LIMIT_MAX
    http_server._RATE_LIMIT_MAX = 3
    http_server._rate_counters.clear()
    try:
        for _ in range(3):
            r = client[0].get("/metrics")
            assert r.status_code == 200
        r = client[0].get("/metrics")
        assert r.status_code == 429
    finally:
        http_server._RATE_LIMIT_MAX = orig
        http_server._rate_counters.clear()


def test_health_bypasses_rate_limit(client, monkeypatch):
    """Health endpoint must never be rate-limited regardless of request volume."""
    from pathly_orchestrator import http_server
    monkeypatch.setenv("PATHLY_FF_RATE_LIMITING", "true")
    orig = http_server._RATE_LIMIT_MAX
    http_server._RATE_LIMIT_MAX = 1
    http_server._rate_counters.clear()
    try:
        for _ in range(5):
            r = client[0].get("/health")
            assert r.status_code == 200, "/health must always return 200 regardless of rate-limit"
    finally:
        http_server._RATE_LIMIT_MAX = orig
        http_server._rate_counters.clear()


def test_next_action_missing_body(client):
    c, _ = client
    # POST with content-type application/json but no body → get_json() returns None → 400
    r = c.post(
        "/next_action",
        data=b"",
        content_type="application/json",
        headers={"Content-Length": "0"},
    )
    # The server returns 400 (Missing JSON body) or 4xx for any malformed request
    assert r.status_code in (400, 415, 500)
    data = json.loads(r.data)
    assert "error" in data


def test_next_action_missing_fields(client):
    c, _ = client
    r = c.post("/next_action", json={})
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data


def test_next_action_invalid_field_type(client):
    c, _ = client
    r = c.post("/next_action", json={"flow": 123, "topic": "t", "project_root": "/p"})
    assert r.status_code == 400


def test_complete_stage_missing_fields(client):
    c, _ = client
    r = c.post("/complete_stage", json={"flow": "team"})
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "Missing fields" in data["error"]


def test_record_activity_missing_fields(client):
    c, _ = client
    r = c.post("/record_activity", json={})
    assert r.status_code == 400
    data = json.loads(r.data)
    assert "error" in data


def test_record_activity_invalid_token_count(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "a", "feature": "f", "summary": "s", "input_tokens": -1},
    )
    assert r.status_code == 400


def test_record_activity_negative_tokens_rejected(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "a", "feature": "f", "summary": "s", "input_tokens": -5},
    )
    assert r.status_code == 400


def test_record_activity_with_wall_seconds(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "builder", "feature": "my-feature", "summary": "done", "wall_seconds": 42, "tool_uses": 5},
    )
    assert r.status_code == 200


def test_record_activity_invalid_wall_seconds(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "a", "feature": "f", "summary": "s", "wall_seconds": -1},
    )
    assert r.status_code == 400


def test_record_activity_with_total_tokens(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "builder", "feature": "f", "summary": "s", "total_tokens": 5000},
    )
    assert r.status_code == 200


def test_record_activity_duration_ms_converts_to_wall_seconds(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "builder", "feature": "f", "summary": "s", "duration_ms": 90000},
    )
    assert r.status_code == 200


def test_record_activity_negative_total_tokens_rejected(client):
    c, _ = client
    r = c.post(
        "/record_activity",
        json={"agent": "a", "feature": "f", "summary": "s", "total_tokens": -1},
    )
    assert r.status_code == 400


def test_record_activity_appends_complete_agent_done_event(client):
    c, tmp = client
    events_dir = tmp / "pathly" / "plans" / "feature-a"
    events_dir.mkdir(parents=True)

    r = c.post(
        "/record_activity",
        json={
            "agent": "builder",
            "feature": "feature-a",
            "summary": "done",
            "project_root": str(tmp),
            "model": "gpt-5",
            "conversation": 2,
            "result": "DONE",
            "total_tokens": 15,
            "input_tokens": 10,
            "output_tokens": 5,
            "tool_uses": 3,
            "duration_ms": 2500,
            "cost_usd": 0.0123,
            "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
            "span_id": "00f067aa0ba902b7",
        },
    )

    assert r.status_code == 200
    event = json.loads((events_dir / "EVENTS.jsonl").read_text().strip())
    assert event["schema_version"] == 1
    assert event["model"] == "gpt-5"
    assert event["conversation"] == 2
    assert event["tokens_in"] == 10
    assert event["tokens_out"] == 5
    assert event["cost_usd"] == 0.0123
    assert event["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert event["span_id"] == "00f067aa0ba902b7"


def test_record_activity_uses_total_tokens_when_split_is_missing(client):
    c, tmp = client
    events_dir = tmp / "pathly" / "plans" / "feature-b"
    events_dir.mkdir(parents=True)

    r = c.post(
        "/record_activity",
        json={
            "agent": "builder",
            "feature": "feature-b",
            "summary": "done",
            "project_root": str(tmp),
            "total_tokens": 15,
            "cost_usd": 0.0,
        },
    )

    assert r.status_code == 200
    event = json.loads((events_dir / "EVENTS.jsonl").read_text().strip())
    assert event["tokens_in"] == 15
    assert event["tokens_out"] == 0
    assert "cost_usd" in event


def test_events_stream_missing_params(client):
    c, _ = client
    r = c.get("/events/stream")
    assert r.status_code == 400


def test_events_stream_path_traversal(client):
    c, tmp = client
    # Use enough traversal segments to escape any project_root on any OS
    traversal = "../../../../../../../../../etc/passwd"
    r = c.get(f"/events/stream?topic={traversal}&project_root={tmp}")
    assert r.status_code == 400


@patch(
    "pathly_orchestrator.http_server.next_action",
    return_value={"current_state": "plan", "agent": "planner", "instructions": "..."},
)
def test_next_action_valid(_, client):
    c, tmp = client
    r = c.post(
        "/next_action",
        json={"flow": "team", "topic": "feat", "project_root": str(tmp)},
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["current_state"] == "plan"


def test_metrics_endpoint(client):
    c, _ = client
    r = c.get("/metrics")
    assert r.status_code == 200
    assert b"pathly_requests_total" in r.data
    assert b"pathly_sse_clients_active" in r.data


def test_events_stream_last_event_id_catchup(tmp_path, monkeypatch):
    """Reconnecting with Last-Event-ID: N only receives events with seq > N.

    Tests the catch-up logic end-to-end by consuming the streaming response in a
    background thread and stopping after the initial catch-up burst is received.
    """
    from pathly_orchestrator import db as _db
    from pathly_orchestrator import http_server as _hs

    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    _hs.app.config["TESTING"] = True
    # Clear any leftover SSE state from other tests
    with _hs._lock:
        _hs._clients.clear()
        _hs._tailers.clear()

    topic = "sse-reconnect-test2"
    feature_dir = tmp_path / "pathly" / "plans" / topic
    feature_dir.mkdir(parents=True)

    # Write 3 events into SQLite: seq 1 (EV_A), seq 2 (EV_B), seq 3 (EV_C)
    conn = _db.get_db(feature_dir)
    _db.append_event(conn, topic, {"type": "EV_A", "msg": "first"})
    _db.append_event(conn, topic, {"type": "EV_B", "msg": "second"})
    _db.append_event(conn, topic, {"type": "EV_C", "msg": "third"})

    received: list[str] = []
    error_holder: list[Exception] = []

    def read_stream():
        try:
            # Use a separate test client instance to avoid state leakage
            with _hs.app.test_client() as sc:
                with sc.get(
                    f"/events/stream?topic={topic}&project_root={tmp_path}",
                    headers={"Last-Event-ID": "1"},
                ) as resp:
                    # Read chunks from the streaming response
                    for chunk in resp.response:
                        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                        received.append(text)
                        # Stop after we have the connected message (catch-up + connected)
                        if '"type":"connected"' in text or 'type":"connected"' in text:
                            break
        except Exception as exc:
            error_holder.append(exc)

    t = threading.Thread(target=read_stream, daemon=True)
    t.start()
    t.join(timeout=5.0)

    assert not error_holder, f"Stream reader raised: {error_holder[0]}"
    body = "".join(received)
    # Events with seq > 1 should appear in the catch-up: EV_B (seq 2) and EV_C (seq 3)
    assert "EV_B" in body
    assert "EV_C" in body
    # EV_A (seq 1) must NOT appear — client already has it
    assert "EV_A" not in body
