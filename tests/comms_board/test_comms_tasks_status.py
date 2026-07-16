"""Guaranteed per-task progress for the SINGLE executor (route-level status posts).

The single drain agent transitions each task through POST /comms/tasks/{claim,complete,fail}.
These handlers must emit a guaranteed `status` post (Started / Done / Failed) at the transition,
so a headless single-agent run shows per-task progress WITHOUT relying on the agent posting it.
(The LOOP executor emits the equivalent supervisor-side via scheduler._post_task_status; the two
paths are disjoint — the loop claims in-process, single via HTTP — so there is no double-post.)
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


def _post_task(client, text: str, scope: str) -> str:
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "builder",
            "type": "task",
            "text": text,
            "board": "feature",
            "scope": scope,
        },
    )
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _make_task_pending(message_id: str) -> None:
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    conn.execute(
        "UPDATE comms_messages SET task_status='pending' WHERE id=?", (message_id,)
    )
    conn.commit()


def _status_texts(scope: str) -> list[str]:
    """Guaranteed supervisor-side status lines posted for a scope, oldest first."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    rows = conn.execute(
        "SELECT text FROM comms_messages WHERE scope=? AND type='status' "
        "AND from_agent='supervisor' AND deleted_at IS NULL ORDER BY id",
        (scope,),
    ).fetchall()
    return [r["text"] for r in rows]


def test_claim_posts_started_status(client):
    """Claiming a pending task posts exactly one 'Started: <task>' status."""
    mid = _post_task(client, "task alpha", scope="st_claim")
    _make_task_pending(mid)

    r = client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "r1"})
    assert json.loads(r.data)["claimed"] is True

    started = [t for t in _status_texts("st_claim") if t.startswith("Started:")]
    assert len(started) == 1, _status_texts("st_claim")
    assert "task alpha" in started[0]


def test_complete_posts_done_status(client):
    """Completing a task posts exactly one 'Done: <task>' status."""
    mid = _post_task(client, "task beta", scope="st_done")
    _make_task_pending(mid)
    client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "r1"})

    r = client.post(
        "/comms/tasks/complete", json={"message_id": mid, "feature": "st_done"}
    )
    assert json.loads(r.data)["ok"] is True

    done = [t for t in _status_texts("st_done") if t.startswith("Done:")]
    assert len(done) == 1, _status_texts("st_done")
    assert "task beta" in done[0]


def test_fail_posts_failed_status_with_reason(client):
    """Failing a task posts a 'Failed: <task> — <reason>' status."""
    mid = _post_task(client, "task gamma", scope="st_fail")
    _make_task_pending(mid)

    r = client.post("/comms/tasks/fail", json={"message_id": mid, "reason": "boom"})
    assert json.loads(r.data)["ok"] is True

    failed = [t for t in _status_texts("st_fail") if t.startswith("Failed:")]
    assert len(failed) == 1, _status_texts("st_fail")
    assert "task gamma" in failed[0] and "boom" in failed[0]


def test_claim_then_complete_posts_exactly_one_each(client):
    """A full claim→complete emits exactly one Started and one Done — no duplication."""
    mid = _post_task(client, "task solo", scope="st_once")
    _make_task_pending(mid)
    client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "r1"})
    client.post("/comms/tasks/complete", json={"message_id": mid, "feature": "st_once"})

    texts = _status_texts("st_once")
    assert len([t for t in texts if t.startswith("Started:")]) == 1, texts
    assert len([t for t in texts if t.startswith("Done:")]) == 1, texts


def test_double_claim_does_not_post_second_started(client):
    """A rejected second claim (already in_progress) must not post another Started."""
    mid = _post_task(client, "task dup", scope="st_dup")
    _make_task_pending(mid)
    client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "r1"})
    client.post("/comms/tasks/claim", json={"message_id": mid, "run_id": "r2"})

    started = [t for t in _status_texts("st_dup") if t.startswith("Started:")]
    assert len(started) == 1, started
