"""Tests for POST /comms/goals/stop.

Covers:
  (1) stop a goal with nothing running → 200 stopped:false reason:not_running
  (2) stop with a board_lock held for the goal's (board,scope) → lock released, stopped:true
  (3) stop a non-existent goal → 404
  (4) stop a non-goal message → 400
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting never spawns background threads during tests."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _make_goal(conn, scope, executor="single", text="Goal: x"):
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text=text,
        executor=executor,
    )


def _make_task(conn, scope, text, goal_id):
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        goal_id=goal_id,
    )


# ---------------------------------------------------------------------------
# (1) Nothing running → stopped:false
# ---------------------------------------------------------------------------


def test_stop_goal_nothing_running(client):
    """Stopping a goal when no run is active returns stopped:false, reason:not_running."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    goal = _make_goal(conn, "gs_idle")

    r = client.post("/comms/goals/stop", json={"goal_id": goal})
    assert r.status_code == 200
    body = json.loads(r.data)
    assert body["ok"] is True
    assert body["stopped"] is False
    assert body["reason"] == "not_running"


# ---------------------------------------------------------------------------
# (2) Board lock held → lock released after stop
# ---------------------------------------------------------------------------


def test_stop_goal_with_board_lock_held(client):
    """Stopping a goal whose board lock is held releases the lock and returns stopped:true."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor import board_lock

    conn = get_db()
    scope = "gs_locked"
    goal = _make_goal(conn, scope)

    run_id = "test-run-id-1234567890"
    board_lock.acquire("feature", scope, run_id)
    try:
        r = client.post("/comms/goals/stop", json={"goal_id": goal})
        assert r.status_code == 200
        body = json.loads(r.data)
        assert body["ok"] is True
        assert body["stopped"] is True
        assert body["how"] == "board_run"
        assert body["run_id"] == run_id
        # Lock must be released after stop
        assert board_lock.holder("feature", scope) is None
    finally:
        # Belt-and-suspenders: ensure lock is released even if assertion fails
        board_lock.release("feature", scope, run_id)


# ---------------------------------------------------------------------------
# (3) Non-existent goal → 404
# ---------------------------------------------------------------------------


def test_stop_goal_not_found(client):
    """Stopping a goal that doesn't exist returns 404."""
    r = client.post("/comms/goals/stop", json={"goal_id": "no-such-goal-id"})
    assert r.status_code == 404
    body = json.loads(r.data)
    assert body["ok"] is False
    assert body["reason"] == "not_found"


# ---------------------------------------------------------------------------
# (4) Non-goal message → 400
# ---------------------------------------------------------------------------


def test_stop_non_goal_message(client):
    """Pointing stop at a task (not a goal) returns 400."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    scope = "gs_nongoal"
    goal = _make_goal(conn, scope)
    task = _make_task(conn, scope, "a task", goal)

    r = client.post("/comms/goals/stop", json={"goal_id": task})
    assert r.status_code == 400
    body = json.loads(r.data)
    assert body["ok"] is False
    assert body["reason"] == "not_goal"


# ---------------------------------------------------------------------------
# (5) Missing / empty goal_id → 400
# ---------------------------------------------------------------------------


def test_stop_goal_missing_goal_id(client):
    r = client.post("/comms/goals/stop", json={})
    assert r.status_code == 400


def test_stop_goal_empty_goal_id(client):
    r = client.post("/comms/goals/stop", json={"goal_id": "   "})
    assert r.status_code == 400
