"""chief-autopilot 11: a task's ``claimed_by`` names the run that works on it.

``POST /comms/tasks/claim`` takes the run id from the caller's live run token, not from the body
(drain-dag claims with the literal ``"$GOAL_ID-single"``); a tokenless caller keeps the body value.
``POST /comms/tasks/run`` claims with the id of the board run it starts. The loop scheduler's own
claims stay ``sched-<task>#N``.
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


def _task(scope: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    tid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text="Build X. Files: a. Done when: b.",
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
        (json.dumps([]), tid),
    )
    conn.commit()
    return tid


def _claimed_by(tid: str):
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT claimed_by FROM comms_messages WHERE id=?", (tid,))
        .fetchone()
    )
    return row["claimed_by"]


def _mint(run_id: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    return mint_run_token(
        get_db(), run_id, "builder", "feat-c", "/proj", "feature", "feat-c"
    )


def test_a_tokened_claim_records_the_token_run_not_the_body(client):
    tid = _task("feat-c")
    token = _mint("run-from-token")
    r = client.post(
        "/comms/tasks/claim",
        json={"message_id": tid, "run_id": "$GOAL_ID-single"},
        headers={"X-Pathly-Run-Token": token},
    )
    assert r.status_code == 200, r.data
    assert r.get_json()["claimed"] is True
    assert _claimed_by(tid) == "run-from-token"


def test_a_tokenless_claim_records_the_body_value(client):
    tid = _task("feat-c")
    r = client.post(
        "/comms/tasks/claim", json={"message_id": tid, "run_id": "body-run-7"}
    )
    assert r.status_code == 200, r.data
    assert r.get_json()["claimed"] is True
    assert _claimed_by(tid) == "body-run-7"


def test_task_run_claims_with_the_id_of_the_run_it_starts(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        # The claim is in place before the run starts, under the id the run is given.
        seen["run_id"] = kw.get("run_id")
        seen["claimed_by_at_start"] = _claimed_by(tid)
        return {"ok": True, "run_id": kw.get("run_id")}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    tid = _task("feat-run")
    r = client.post("/comms/tasks/run", json={"message_id": tid})
    assert r.status_code == 200, r.data
    run_id = r.get_json()["run_id"]
    assert run_id and seen["run_id"] == run_id
    assert seen["claimed_by_at_start"] == run_id
    assert _claimed_by(tid) == run_id


def test_start_board_run_uses_the_run_id_it_is_given():
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.board_run import start_board_run

    out = start_board_run(
        "feature",
        "feat-given",
        "single-agent",
        run_id="given-run-1",
        spawn_fn=lambda *a, **k: {"result": "ok"},
        block=True,
    )
    assert out["ok"] is True and out["run_id"] == "given-run-1"
    assert board_lock.holder("feature", "feat-given") is None


def test_a_loop_scheduler_claim_records_its_sched_id():
    from pathly_orchestrator.supervisor.isolation import LaneIsolation
    from pathly_orchestrator.supervisor.scheduler import scheduler_loop

    class _State:
        project_root = "/repo"
        db_path = ""
        fsm_port = 8765
        current_adapter = "claude"
        model = "claude-sonnet-4-6"

    tid = _task("feat-sched")
    seen: dict = {}

    def _spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        seen["run_id"] = run_id
        seen["claimed_by"] = _claimed_by(tid)
        return {"result": "ok"}

    out = scheduler_loop(
        _State(),
        board="feature",
        scope="feat-sched",
        isolation=LaneIsolation(),
        spawn_fn=_spawn,
    )
    assert tid in out["completed"]
    assert seen["run_id"] == f"sched-{tid}#1"
    assert seen["claimed_by"] == f"sched-{tid}#1"
