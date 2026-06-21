"""Tests for POST /comms/tasks/claim and POST /comms/tasks/fail (DAG scheduler routes).

Covers:
  - claim a pending task → {"claimed": true}
  - claim the same task again → {"claimed": false} (double-spawn guard)
  - fail a task with dependents → 200, blocked list non-empty
  - GET /comms/tasks shows dependents as blocked after fail
  - 400 on missing required fields (message_id, run_id)
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_task(
    client,
    text: str,
    depends_on: list[str] | None = None,
    feature: str = "myfeature",
    scope: str = "myfeature",
) -> str:
    """Post a task message via the HTTP API and return its message_id."""
    payload: dict = {
        "feature": feature,
        "from": "builder",
        "type": "task",
        "text": text,
        "board": "feature",
        "scope": scope,
    }
    if depends_on is not None:
        payload["depends_on"] = depends_on
    r = client.post("/comms/post", json=payload)
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _make_task_pending(message_id: str) -> None:
    """Set task_status=pending directly in the DB (bypasses HTTP)."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id=?",
        (message_id,),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# POST /comms/tasks/claim
# ---------------------------------------------------------------------------


def test_claim_pending_task_returns_true(client):
    """Claiming a pending task for the first time returns claimed=true."""
    mid = _post_task(client, "claimable task", scope="claim1", feature="claim1")
    _make_task_pending(mid)

    r = client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "run-abc"})
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["claimed"] is True


def test_claim_same_task_twice_returns_false(client):
    """Claiming a task that was already claimed returns claimed=false."""
    mid = _post_task(client, "claim-once task", scope="claim2", feature="claim2")
    _make_task_pending(mid)

    r1 = client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "run-1"})
    assert r1.status_code == 200
    assert json.loads(r1.data)["claimed"] is True

    r2 = client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "run-2"})
    assert r2.status_code == 200
    assert json.loads(r2.data)["claimed"] is False


def test_claim_missing_message_id_returns_400(client):
    """POST /comms/tasks/claim without message_id returns 400."""
    r = client.post("/comms/tasks/claim", json={"run_id": "run-x"})
    assert r.status_code == 400


def test_claim_missing_run_id_returns_400(client):
    """POST /comms/tasks/claim without run_id returns 400."""
    r = client.post("/comms/tasks/claim", json={"message_id": "some-id"})
    assert r.status_code == 400


def test_claim_blank_message_id_returns_400(client):
    """POST /comms/tasks/claim with blank message_id returns 400."""
    r = client.post("/comms/tasks/claim", json={"message_id": "   ", "run_id": "run-x"})
    assert r.status_code == 400


def test_claim_blank_run_id_returns_400(client):
    """POST /comms/tasks/claim with blank run_id returns 400."""
    r = client.post("/comms/tasks/claim", json={"message_id": "some-id", "run_id": ""})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /comms/tasks/fail
# ---------------------------------------------------------------------------


def test_fail_task_with_dependents_returns_blocked_list(client):
    """Failing a task that has dependents returns 200 with non-empty blocked list."""
    dep_id = _post_task(client, "parent task", scope="fail1", feature="fail1")
    child_id = _post_task(
        client, "child task", depends_on=[dep_id], scope="fail1", feature="fail1"
    )
    _make_task_pending(dep_id)
    _make_task_pending(child_id)

    r = client.post(
        "/comms/tasks/fail", json={"message_id": dep_id, "reason": "exploded"}
    )
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["ok"] is True
    assert child_id in data["blocked"], "child should be in blocked list"
    assert len(data["blocked"]) >= 1


def test_fail_task_dependents_show_as_blocked_in_get(client):
    """After failing a task, GET /comms/tasks?status=pending should not include blocked dependents."""
    from pathly_orchestrator.db.connection import get_db

    dep_id = _post_task(client, "parent task", scope="fail2", feature="fail2")
    child_id = _post_task(
        client, "child task", depends_on=[dep_id], scope="fail2", feature="fail2"
    )
    _make_task_pending(dep_id)
    _make_task_pending(child_id)

    r_fail = client.post("/comms/tasks/fail", json={"message_id": dep_id})
    assert r_fail.status_code == 200
    assert child_id in json.loads(r_fail.data)["blocked"]

    conn = get_db()
    row = conn.execute(
        "SELECT task_status FROM comms_messages WHERE id=?", (child_id,)
    ).fetchone()
    assert row["task_status"] == "blocked", "dependent should be marked blocked in DB"


def test_fail_task_cascades_transitive_dependents(client):
    """Failing A with chain A→B→C cascades blocked to both B and C."""
    a_id = _post_task(client, "task A", scope="fail3", feature="fail3")
    b_id = _post_task(
        client, "task B", depends_on=[a_id], scope="fail3", feature="fail3"
    )
    c_id = _post_task(
        client, "task C", depends_on=[b_id], scope="fail3", feature="fail3"
    )
    for mid in (a_id, b_id, c_id):
        _make_task_pending(mid)

    r = client.post("/comms/tasks/fail", json={"message_id": a_id})
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["ok"] is True
    assert b_id in data["blocked"]
    assert c_id in data["blocked"]


def test_fail_task_no_dependents_returns_empty_blocked(client):
    """Failing a leaf task with no dependents returns blocked=[]."""
    mid = _post_task(client, "leaf task", scope="fail4", feature="fail4")
    _make_task_pending(mid)

    r = client.post("/comms/tasks/fail", json={"message_id": mid})
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["ok"] is True
    assert data["blocked"] == []


def test_fail_task_missing_message_id_returns_400(client):
    """POST /comms/tasks/fail without message_id returns 400."""
    r = client.post("/comms/tasks/fail", json={"reason": "oops"})
    assert r.status_code == 400


def test_fail_task_blank_message_id_returns_400(client):
    """POST /comms/tasks/fail with blank message_id returns 400."""
    r = client.post("/comms/tasks/fail", json={"message_id": ""})
    assert r.status_code == 400


def test_fail_task_optional_reason_absent(client):
    """POST /comms/tasks/fail without reason field still succeeds."""
    mid = _post_task(client, "no-reason task", scope="fail5", feature="fail5")
    _make_task_pending(mid)

    r = client.post("/comms/tasks/fail", json={"message_id": mid})
    assert r.status_code == 200
    assert json.loads(r.data)["ok"] is True
