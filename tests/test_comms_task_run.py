"""POST /comms/tasks/run — ad-hoc single-task execution from the Goals & Tasks view.

Claims the task, spawns a builder on its prompt via start_board_run, completes on success.
start_board_run is stubbed so no real PTY/agent launches.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _goal(conn, scope):
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(conn, board="feature", scope=scope, from_agent="planner", type="goal", text="G")


def _task(conn, scope, gid, text="Build X. Files: a. Done when: b.", status="pending", deps=None):
    from pathly_orchestrator.db.queries.comms import post_message

    tid = post_message(conn, board="feature", scope=scope, from_agent="planner", type="task", text=text, goal_id=gid)
    conn.execute(
        "UPDATE comms_messages SET task_status=?, depends_on=? WHERE id=?",
        (status, json.dumps(deps or []), tid),
    )
    conn.commit()
    return tid


def test_run_task_claims_and_spawns(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br
    from pathly_orchestrator.db.connection import get_db

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        seen.update(board=board, scope=scope, mode=mode, instructions=kw.get("instructions"), skill=kw.get("skill"))
        return {"ok": True, "run_id": "r1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    conn = get_db()
    gid = _goal(conn, "taskrun-ok")
    tid = _task(conn, "taskrun-ok", gid, text="Build the widget. Files: w.py. Done when: tests pass.")

    r = client.post("/comms/tasks/run", json={"message_id": tid, "project_root": "/tmp/p"})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True and body["run_id"] == "r1"

    # Claimed → in_progress, and the builder got the task's own prompt via a single-agent build.
    st = conn.execute("SELECT task_status FROM comms_messages WHERE id=?", (tid,)).fetchone()["task_status"]
    assert st == "in_progress"
    assert seen["mode"] == "single-agent"
    assert seen["skill"] == "development/build"
    assert "Build the widget" in seen["instructions"]


def test_run_task_rejects_done(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br
    from pathly_orchestrator.db.connection import get_db

    def _boom(*a, **k):  # must NOT be called
        raise AssertionError("start_board_run should not run for a done task")

    monkeypatch.setattr(_br, "start_board_run", _boom)
    conn = get_db()
    gid = _goal(conn, "taskrun-done")
    tid = _task(conn, "taskrun-done", gid, status="done")

    r = client.post("/comms/tasks/run", json={"message_id": tid})
    assert r.status_code == 409
    assert r.get_json()["reason"] == "already_done"


def test_run_task_not_found(client):
    r = client.post("/comms/tasks/run", json={"message_id": "does-not-exist"})
    assert r.status_code == 404


def test_run_task_rejects_goal_id(client):
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    gid = _goal(conn, "taskrun-notatask")
    r = client.post("/comms/tasks/run", json={"message_id": gid})
    assert r.status_code == 400
    assert r.get_json()["reason"] == "not_task"


def test_stop_task_reverts_to_pending(client):
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    gid = _goal(conn, "taskstop")
    tid = _task(conn, "taskstop", gid, status="in_progress")  # simulate a running task
    r = client.post("/comms/tasks/stop", json={"message_id": tid})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    st = conn.execute("SELECT task_status FROM comms_messages WHERE id=?", (tid,)).fetchone()["task_status"]
    assert st == "pending"


def test_run_task_releases_claim_on_spawn_refusal(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br
    from pathly_orchestrator.db.connection import get_db

    monkeypatch.setattr(_br, "start_board_run", lambda *a, **k: {"ok": False, "reason": "board_busy"})
    conn = get_db()
    gid = _goal(conn, "taskrun-busy")
    tid = _task(conn, "taskrun-busy", gid)

    r = client.post("/comms/tasks/run", json={"message_id": tid})
    assert r.status_code == 409
    # The claim must be released so the task can be retried.
    st = conn.execute("SELECT task_status FROM comms_messages WHERE id=?", (tid,)).fetchone()["task_status"]
    assert st == "pending"
