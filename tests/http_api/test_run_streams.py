"""GET /events/runs?run_id= — the unified per-run SSE feed (unified-control-plane T3).

Exercises the new control blueprint's run-scoped stream: `_broadcast_run_event` delivers
only to a client subscribed under the matching run_id (filters out other run_ids);
`_broadcast_runner`/`_broadcast_comms` (the existing /events/runner and /events/comms
sinks) tee any payload that carries a run_id onto the same channel; and the endpoint
itself streams a real SSE connection end-to-end (mirrors
test_http_server.test_events_stream_last_event_id_catchup's background-thread read
pattern — /events/runner has no existing dedicated test to mirror instead).
"""

from __future__ import annotations

import queue as _queue
import threading

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _clean_run_clients():
    """_run_clients is keyed by run_id (unique per run, never reused) — clear leftovers
    around each test so one test's queue can never receive another test's broadcast."""
    from pathly_orchestrator.http_server.sse import _run_clients, _run_lock

    with _run_lock:
        _run_clients.clear()
    yield
    with _run_lock:
        _run_clients.clear()


def test_run_events_missing_run_id_is_400(client):
    resp = client.get("/events/runs")
    assert resp.status_code == 400


def test_broadcast_run_event_filters_by_run_id():
    """A queue registered under run_id A never receives a broadcast for run_id B."""
    from pathly_orchestrator.http_server.sse import (
        _broadcast_run_event,
        _run_clients,
        _run_lock,
    )

    qa: _queue.Queue = _queue.Queue(maxsize=10)
    qb: _queue.Queue = _queue.Queue(maxsize=10)
    with _run_lock:
        _run_clients["run-a"] = [qa]
        _run_clients["run-b"] = [qb]

    _broadcast_run_event("run-a", {"type": "STAGE_RESULT", "run_id": "run-a"})

    raw = qa.get_nowait()
    assert "STAGE_RESULT" in raw
    assert qa.empty()
    assert qb.empty()  # run-b's client did NOT receive run-a's event


def test_broadcast_run_event_empty_run_id_is_noop():
    from pathly_orchestrator.http_server.sse import _broadcast_run_event, _run_clients

    _broadcast_run_event("", {"type": "STAGE_RESULT"})  # must not raise
    assert _run_clients == {}


def test_broadcast_runner_tees_to_run_channel_when_payload_has_run_id():
    """_broadcast_runner (the existing /events/runner sink) also feeds /events/runs."""
    from pathly_orchestrator.http_server.sse import (
        _broadcast_runner,
        _run_clients,
        _run_lock,
    )

    q: _queue.Queue = _queue.Queue(maxsize=10)
    with _run_lock:
        _run_clients["run-teed-1"] = [q]

    _broadcast_runner("some-topic", {"type": "STAGE_RESULT", "run_id": "run-teed-1"})

    raw = q.get_nowait()
    assert "run-teed-1" in raw


def test_broadcast_runner_without_run_id_does_not_touch_run_channel():
    from pathly_orchestrator.http_server.sse import _broadcast_runner, _run_clients

    _broadcast_runner("some-topic", {"type": "TOAST", "level": "info", "message": "hi"})
    assert _run_clients == {}


def test_broadcast_comms_tees_to_run_channel_when_payload_has_run_id():
    """_broadcast_comms (the existing /events/comms sink) also feeds /events/runs."""
    from pathly_orchestrator.http_server.sse import (
        _broadcast_comms,
        _run_clients,
        _run_lock,
    )

    q: _queue.Queue = _queue.Queue(maxsize=10)
    with _run_lock:
        _run_clients["run-teed-2"] = [q]

    _broadcast_comms("some-scope", {"type": "COMMS_UPDATE", "run_id": "run-teed-2"})

    raw = q.get_nowait()
    assert "run-teed-2" in raw


def test_run_events_endpoint_streams_a_live_broadcast():
    """End-to-end: connect to /events/runs?run_id=X, then a same-run_id broadcast arrives
    over the wire. The streaming body blocks on queue.get, so it must be consumed off the
    main thread (mirrors test_events_stream_last_event_id_catchup)."""
    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.http_server.sse import _broadcast_run_event

    app.config["TESTING"] = True
    run_id = "run-live-e2e"
    received: list[str] = []
    connected = threading.Event()
    error_holder: list[Exception] = []

    def read_stream():
        try:
            with app.test_client() as sc:
                with sc.get(f"/events/runs?run_id={run_id}") as resp:
                    for chunk in resp.response:
                        text = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
                        received.append(text)
                        if "connected" in text:
                            connected.set()
                        if "MY_EVENT" in text:
                            break
        except Exception as exc:
            error_holder.append(exc)

    t = threading.Thread(target=read_stream, daemon=True)
    t.start()
    assert connected.wait(timeout=5.0), "stream never reported connected"
    _broadcast_run_event(run_id, {"type": "MY_EVENT", "run_id": run_id})
    t.join(timeout=5.0)

    assert not error_holder, f"Stream reader raised: {error_holder[0]}"
    assert any("MY_EVENT" in chunk for chunk in received), received
