"""Tests for Phase 0b — goal_id + executor on the comms write path.

Covers (mirrors test_comms_dag.py's shape):
  - Round-trip: a type='task' with goal_id+executor AND a type='goal' with
    executor persist non-null through POST → GET.
  - goal_id that is not a string → 400.
  - executor that is not a string → 400.
  - A task with NO goal_id/executor → 200 with NULL columns (back-compat).

These exercise the new columns added by the 0a migration; the {single,loop,team}
executor enum is enforced downstream by the Phase-1 dispatcher, not here.
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


def _get_message(client, feature: str, scope: str, message_id: str) -> dict:
    """Fetch the board for scope and return the row with the given id."""
    r = client.get(f"/comms?feature={feature}&scope={scope}&limit=100")
    assert r.status_code == 200, r.data
    rows = json.loads(r.data)
    match = [m for m in rows if m["id"] == message_id]
    assert match, f"message {message_id} not found in board {scope}"
    return match[0]


# ---------------------------------------------------------------------------
# Round-trip — goal_id + executor persist
# ---------------------------------------------------------------------------


def test_goal_and_task_roundtrip_non_null(client):
    """A goal (executor) and a task (goal_id + executor) both persist non-null."""
    feature = scope = "ge_roundtrip"

    # 1. Post the goal first, capture its id as the goal_id.
    rg = client.post(
        "/comms/post",
        json={
            "feature": feature,
            "from": "planner",
            "type": "goal",
            "text": "Goal: ge_roundtrip",
            "board": "feature",
            "scope": scope,
            "executor": "single",
        },
    )
    assert rg.status_code == 200, rg.data
    goal_id = json.loads(rg.data)["message_id"]

    # 2. Post a task stamped with that goal_id (executor is write-path-agnostic).
    rt = client.post(
        "/comms/post",
        json={
            "feature": feature,
            "from": "planner",
            "type": "task",
            "text": "Phase 1: do the thing",
            "board": "feature",
            "scope": scope,
            "stage": "BUILDING",
            "conv": 1,
            "goal_id": goal_id,
            "executor": "team",
        },
    )
    assert rt.status_code == 200, rt.data
    task_id = json.loads(rt.data)["message_id"]

    goal_row = _get_message(client, feature, scope, goal_id)
    assert goal_row["type"] == "goal"
    assert goal_row["executor"] == "single"
    assert goal_row["goal_id"] is None, "the goal itself carries no goal_id"

    task_row = _get_message(client, feature, scope, task_id)
    assert task_row["type"] == "task"
    assert task_row["goal_id"] == goal_id
    assert task_row["executor"] == "team"


# ---------------------------------------------------------------------------
# Negative path — type guards return 400
# ---------------------------------------------------------------------------


def test_goal_id_non_string_rejected(client):
    """A non-string goal_id is rejected with 400."""
    r = client.post(
        "/comms/post",
        json={
            "feature": "ge_bad",
            "from": "planner",
            "type": "task",
            "text": "bad goal_id",
            "board": "feature",
            "scope": "ge_bad",
            "goal_id": 123,
        },
    )
    assert r.status_code == 400, r.data
    assert "goal_id" in json.loads(r.data)["error"]


def test_executor_non_string_rejected(client):
    """A non-string executor is rejected with 400."""
    r = client.post(
        "/comms/post",
        json={
            "feature": "ge_bad",
            "from": "planner",
            "type": "goal",
            "text": "bad executor",
            "board": "feature",
            "scope": "ge_bad",
            "executor": ["team"],
        },
    )
    assert r.status_code == 400, r.data
    assert "executor" in json.loads(r.data)["error"]


# ---------------------------------------------------------------------------
# Back-compat — a task without the new fields posts fine with NULL columns
# ---------------------------------------------------------------------------


def test_task_without_goal_fields_is_back_compat(client):
    """A task with no goal_id/executor posts 200 and leaves both columns NULL."""
    feature = scope = "ge_backcompat"
    r = client.post(
        "/comms/post",
        json={
            "feature": feature,
            "from": "builder",
            "type": "task",
            "text": "legacy task",
            "board": "feature",
            "scope": scope,
        },
    )
    assert r.status_code == 200, r.data
    task_id = json.loads(r.data)["message_id"]

    row = _get_message(client, feature, scope, task_id)
    assert row["goal_id"] is None
    assert row["executor"] is None
    # The DAG frontier still picks it up — unchanged by the new columns.
    assert row["task_status"] == "pending"


# ---------------------------------------------------------------------------
# Phase 1 — get_ready_tasks goal_id filter (one scope, two goals)
# ---------------------------------------------------------------------------


def test_get_ready_tasks_filters_by_goal():
    """With two goals sharing a scope, the frontier is per-goal when goal_id is given."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_ready_tasks, post_message

    conn = get_db()
    scope = "ge_two_goals"
    g1 = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text="Goal 1",
        executor="single",
    )
    g2 = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text="Goal 2",
        executor="loop",
    )
    t1 = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text="g1 task",
        goal_id=g1,
    )
    t2 = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text="g2 task",
        goal_id=g2,
    )

    # Unfiltered: both tasks are ready (board+scope behavior, unchanged).
    all_ready = {
        r["id"] for r in get_ready_tasks(conn, boards=["feature"], scopes=[scope])
    }
    assert {t1, t2} <= all_ready

    # Filtered to goal 1: only goal 1's task.
    g1_ready = {
        r["id"]
        for r in get_ready_tasks(conn, boards=["feature"], scopes=[scope], goal_id=g1)
    }
    assert t1 in g1_ready
    assert t2 not in g1_ready
