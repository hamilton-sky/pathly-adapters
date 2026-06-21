"""The topic-independent terminal spawn channel.

Regression cover for the board-run bug where TERMINAL_SPAWN was only delivered to
clients subscribed to the broadcast topic — so a run started from a board whose
topic was not the active one never opened a PTY (terminal_spawn_timeout). The fix:
_broadcast_runner mirrors terminal-lifecycle events to a flat, topic-independent
spawn channel that Studio subscribes to exactly once.
"""

import queue

import pytest

from pathly_orchestrator.http_server import sse


@pytest.fixture(autouse=True)
def _clean_registries():
    sse._spawn_clients.clear()
    sse._runner_clients.clear()
    yield
    sse._spawn_clients.clear()
    sse._runner_clients.clear()


def _subscribe_spawn() -> queue.Queue:
    q: queue.Queue = queue.Queue(maxsize=50)
    sse._spawn_clients.append(q)
    return q


def test_spawn_reaches_subscriber_regardless_of_topic():
    q = _subscribe_spawn()
    # No runner client is registered for this topic at all.
    sse._broadcast_runner(
        "feature-X",
        {"type": "TERMINAL_SPAWN", "tab_id": "runner-1", "topic": "feature-X"},
    )
    assert not q.empty()
    assert "TERMINAL_SPAWN" in q.get_nowait()


def test_kill_and_signal_also_mirror():
    q = _subscribe_spawn()
    sse._broadcast_runner("global", {"type": "TERMINAL_KILL", "tab_id": "runner-2"})
    sse._broadcast_runner(
        "project", {"type": "TERMINAL_SIGNAL", "tab_id": "runner-3", "signal": "term"}
    )
    types = [q.get_nowait() for _ in range(2)]
    assert any("TERMINAL_KILL" in t for t in types)
    assert any("TERMINAL_SIGNAL" in t for t in types)


def test_non_terminal_events_do_not_reach_spawn_channel():
    q = _subscribe_spawn()
    sse._broadcast_runner("t", {"type": "COST_UPDATE", "cost_usd": 1})
    sse._broadcast_runner("t", {"type": "STAGE_CHANGE", "stage": "BUILDING"})
    assert q.empty()


def test_topic_channel_still_delivers_to_its_own_subscribers():
    # The per-topic runner channel keeps working for stage/cost events.
    rq: queue.Queue = queue.Queue(maxsize=50)
    sse._runner_clients.setdefault("feature-Y", []).append(rq)
    spawn_q = _subscribe_spawn()
    sse._broadcast_runner(
        "feature-Y",
        {"type": "TERMINAL_SPAWN", "tab_id": "runner-4", "topic": "feature-Y"},
    )
    # Reaches BOTH the topic subscriber and the global spawn channel.
    assert not rq.empty()
    assert not spawn_q.empty()
