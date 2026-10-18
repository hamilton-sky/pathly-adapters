"""`sse._broadcast_runner` sends a spawn's raw run token only on /events/spawn.

A `TERMINAL_SPAWN` payload carries the spawn's `run_token`. `_broadcast_runner` puts the
payload on three channels: the topic's /events/runner clients, every /events/spawn client
and the run's /events/runs clients. None of the /events/ streams needs credentials, and
only the spawn hosts read the token, both from /events/spawn. So the /events/runner and
/events/runs copies must never carry a `run_token` key, the /events/spawn copy keeps it
unchanged, and the caller's dict (reused by callers) is not mutated.
"""

from __future__ import annotations

import json
import queue as _queue

import pytest

TOPIC = "strip-topic"
RUN_ID = "strip-run-1"
MARKER = "marker-token-7f3a9c1e5b"


@pytest.fixture()
def channels():
    """One queue on each of the three registries, restored afterwards."""
    from pathly_orchestrator.http_server import sse

    runner_q: _queue.Queue = _queue.Queue(maxsize=10)
    spawn_q: _queue.Queue = _queue.Queue(maxsize=10)
    run_q: _queue.Queue = _queue.Queue(maxsize=10)
    with sse._runner_lock:
        saved_runner = dict(sse._runner_clients)
        sse._runner_clients.clear()
        sse._runner_clients[TOPIC] = [runner_q]
    with sse._spawn_lock:
        saved_spawn = list(sse._spawn_clients)
        sse._spawn_clients[:] = [spawn_q]
    with sse._run_lock:
        saved_run = dict(sse._run_clients)
        sse._run_clients.clear()
        sse._run_clients[RUN_ID] = [run_q]
    yield {"runner": runner_q, "spawn": spawn_q, "run": run_q}
    with sse._runner_lock:
        sse._runner_clients.clear()
        sse._runner_clients.update(saved_runner)
    with sse._spawn_lock:
        sse._spawn_clients[:] = saved_spawn
    with sse._run_lock:
        sse._run_clients.clear()
        sse._run_clients.update(saved_run)


def _spawn_payload() -> dict:
    return {
        "type": "TERMINAL_SPAWN",
        "tab_id": "tab-1",
        "run_id": RUN_ID,
        "run_token": MARKER,
        "label": "builder",
        "cwd": "/tmp/project",
        "argv": ["claude", "-p", "x"],
        "adapter": "claude",
    }


def test_terminal_spawn_token_reaches_only_the_spawn_channel(channels):
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    _broadcast_runner(TOPIC, _spawn_payload())

    spawn_raw = channels["spawn"].get_nowait()
    assert json.loads(spawn_raw)["run_token"] == MARKER

    for name in ("runner", "run"):
        raw = channels[name].get_nowait()
        assert MARKER not in raw, f"/events/{name} copy carries the raw token"
        assert "run_token" not in json.loads(raw)


def test_stripped_copies_keep_every_other_field(channels):
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    payload = _spawn_payload()
    _broadcast_runner(TOPIC, payload)

    expected = {k: v for k, v in payload.items() if k != "run_token"}
    assert json.loads(channels["runner"].get_nowait()) == expected
    assert json.loads(channels["run"].get_nowait()) == expected
    assert json.loads(channels["spawn"].get_nowait()) == payload


def test_the_callers_payload_still_has_its_token(channels):
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    payload = _spawn_payload()
    _broadcast_runner(TOPIC, payload)

    assert payload["run_token"] == MARKER
    assert payload == _spawn_payload()


def test_a_none_token_is_stripped_from_the_non_spawn_copies_too(channels):
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    payload = _spawn_payload()
    payload["run_token"] = None
    _broadcast_runner(TOPIC, payload)

    assert json.loads(channels["spawn"].get_nowait())["run_token"] is None
    assert "run_token" not in json.loads(channels["runner"].get_nowait())
    assert "run_token" not in json.loads(channels["run"].get_nowait())


def test_an_event_without_the_key_is_delivered_unchanged_everywhere(channels):
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    payload = {"type": "TERMINAL_KILL", "tab_id": "tab-1", "run_id": RUN_ID}
    _broadcast_runner(TOPIC, payload)

    for name in ("runner", "spawn", "run"):
        assert json.loads(channels[name].get_nowait()) == payload, name
    assert payload == {"type": "TERMINAL_KILL", "tab_id": "tab-1", "run_id": RUN_ID}


def test_a_non_spawn_event_is_delivered_unchanged_on_topic_and_run(channels):
    from pathly_orchestrator.http_server.sse import _broadcast_runner

    payload = {"type": "STAGE_RESULT", "run_id": RUN_ID, "stage": "BUILDING"}
    _broadcast_runner(TOPIC, payload)

    assert json.loads(channels["runner"].get_nowait()) == payload
    assert json.loads(channels["run"].get_nowait()) == payload
    assert channels["spawn"].empty()
