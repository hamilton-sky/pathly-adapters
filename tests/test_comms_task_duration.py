"""Tests for board-context-pull Solution B — task claim→complete duration.

Covers:
  (1) A claimed-then-completed task exposes a non-negative duration_seconds on
      GET /comms/tasks, and completed_at is stamped.
  (2) A task that was never claimed has duration_seconds == None (back-compat).
  (3) A failed task's duration is derived from failed_at.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post_task(client, scope: str, text: str = "do it") -> str:
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "planner",
            "type": "task",
            "text": text,
            "board": "feature",
            "scope": scope,
        },
    )
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _get_task(client, scope: str, task_id: str) -> dict:
    r = client.get(f"/comms/tasks?feature={scope}&board=feature&scope={scope}")
    assert r.status_code == 200, r.data
    rows = json.loads(r.data)
    match = [t for t in rows if t["id"] == task_id]
    assert match, f"task {task_id} not in /comms/tasks response"
    return match[0]


def test_completed_task_has_duration(client):
    scope = "dur_done"
    tid = _post_task(client, scope)

    r = client.post(
        "/comms/tasks/claim", json={"message_id": tid, "run_id": "run-1"}
    )
    assert r.status_code == 200 and json.loads(r.data)["claimed"] is True

    r = client.post("/comms/tasks/complete", json={"message_id": tid, "scope": scope})
    assert r.status_code == 200, r.data

    task = _get_task(client, scope, tid)
    assert task.get("completed_at"), "completed_at must be stamped on complete"
    dur = task.get("duration_seconds")
    assert dur is not None and isinstance(dur, (int, float))
    assert dur >= 0


def test_unclaimed_task_duration_is_none(client):
    scope = "dur_pending"
    tid = _post_task(client, scope)
    task = _get_task(client, scope, tid)
    assert task.get("duration_seconds") is None


def test_failed_task_duration_from_failed_at(client):
    scope = "dur_failed"
    tid = _post_task(client, scope)

    r = client.post(
        "/comms/tasks/claim", json={"message_id": tid, "run_id": "run-2"}
    )
    assert r.status_code == 200 and json.loads(r.data)["claimed"] is True

    r = client.post(
        "/comms/tasks/fail", json={"message_id": tid, "reason": "boom"}
    )
    assert r.status_code == 200, r.data

    task = _get_task(client, scope, tid)
    dur = task.get("duration_seconds")
    assert dur is not None and dur >= 0
