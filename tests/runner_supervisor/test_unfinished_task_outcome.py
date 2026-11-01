"""chief-autopilot 05: a single run that leaves its task unfinished is failed, and the task is freed.

A board/single run whose agent claimed a task (drain-dag's literal claim body, with the spawn's
run token) and ended with that task still ``in_progress`` must not end ``success``:

* no ``AGENT_DONE`` from the agent: the synthetic one says ``outcome: failed``,
  ``error: task_unfinished``;
* the agent's own ``AGENT_DONE`` says ``success``: a ``RUN_OUTCOME`` event says failed instead,
  ``GET /runs/<id>`` reports it, and the run keeps exactly one ``agent_invocations`` row;
* the run's ``run_history`` status is ``error``;
* the task goes back to ``pending`` (``fail_reason='task_unfinished'``) and the next run claims
  it; at ``goal.task_max_attempts`` it is failed, its dependents blocked and an escalation posted.

A run whose task is ``done`` keeps ``success``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pathly_orchestrator.supervisor.registry import get_run
from pathly_orchestrator.supervisor.state import RunnerState

SCOPE = "feat-unf"
DRAIN_DAG_CLAIM = {"run_id": "$GOAL_ID-single"}


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _no_reconciliation_window(monkeypatch):
    """The early-advance path starts a billing window that waits for the PTY; none comes here."""
    import pathly_orchestrator.supervisor.terminal as _terminal
    from pathly_orchestrator.supervisor.registry import drop_run

    monkeypatch.setattr(
        _terminal, "_reconciliation_window", lambda run, *a, **k: drop_run(run.run_id)
    )


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _state(tmp_path: Path) -> RunnerState:
    storage = tmp_path / "pathly" / "features" / SCOPE
    storage.mkdir(parents=True, exist_ok=True)
    state = RunnerState(
        topic=SCOPE,
        flow="board-run",
        project_root=str(tmp_path),
        model="claude-sonnet-4-6",
        timeout=60,
        run_id="unused",
        current_state="builder",
        board_scope=SCOPE,
    )
    state.executor_owned_telemetry = True
    state.interactive = False
    state.storage_path = str(storage)
    return state


def _task(text: str = "Build X. Files: a. Done when: b.", deps=None) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    tid = post_message(
        conn, board="feature", scope=SCOPE, from_agent="planner", type="task", text=text
    )
    conn.execute(
        "UPDATE comms_messages SET task_status='pending', depends_on=? WHERE id=?",
        (json.dumps(deps or []), tid),
    )
    conn.commit()
    return tid


def _row(tid: str) -> dict:
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute(
            "SELECT task_status, claimed_by, attempts, fail_reason FROM comms_messages "
            "WHERE id=?",
            (tid,),
        )
        .fetchone()
    )
    return dict(row)


def _spawn(
    client,
    tmp_path: Path,
    run_id: str,
    tid: str,
    *,
    own_agent_done: bool = False,
    finish_task: bool = False,
    pty_first: bool = True,
    exit_code: int = 0,
    agent_done_run_id: str = "",
    agent_done_outcome: str = "success",
) -> dict:
    """Run one board spawn. Its agent claims ``tid`` with drain-dag's literal body and its run
    token, optionally marks it done, optionally writes its own success AGENT_DONE, then ends.
    """
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.terminal import _run_stage_via_terminal

    state = _state(tmp_path)
    seen: dict = {}

    def broadcast(_topic, payload):
        if payload.get("type") != "TERMINAL_SPAWN":
            return
        r = client.post(
            "/comms/tasks/claim",
            json={"message_id": tid, **DRAIN_DAG_CLAIM},
            headers={"X-Pathly-Run-Token": payload["run_token"]},
        )
        seen["claim"] = r.get_json()
        if finish_task:
            conn = get_db()
            conn.execute(
                "UPDATE comms_messages SET task_status='done' WHERE id=?", (tid,)
            )
            conn.commit()
        if own_agent_done:
            eventlog.append_event(
                state.storage_path,
                {
                    "type": "AGENT_DONE",
                    "agent": "builder",
                    "run_id": agent_done_run_id or run_id,
                    "outcome": agent_done_outcome,
                    "summary": "all done",
                    "cost_usd": 0.5,
                    "tokens_in": 10,
                    "tokens_out": 20,
                },
            )
        run = get_run(run_id)
        assert run is not None
        run.mark_started()
        if pty_first:
            run.mark_pty_result({"result": {}, "exit_code": exit_code})

    seen["result"] = _run_stage_via_terminal(
        state, "drain the dag", "claude", "m", run_id, broadcast
    )
    return seen


def _detail(client, run_id: str) -> dict:
    r = client.get(f"/runs/{run_id}")
    assert r.status_code == 200, r.data
    return r.get_json()["run"]


def _last_agent_done(run_id: str) -> dict:
    from pathly_orchestrator.db.connection import get_db

    rows = (
        get_db()
        .execute(
            "SELECT payload FROM fsm_events WHERE event_type='AGENT_DONE' ORDER BY seq"
        )
        .fetchall()
    )
    mine = [json.loads(r["payload"]) for r in rows]
    mine = [p for p in mine if p.get("run_id") == run_id]
    assert mine, "no AGENT_DONE for the run"
    return mine[-1]


def _invocation_rows(run_id: str) -> int:
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT COUNT(*) n FROM agent_invocations WHERE run_id=?", (run_id,))
        .fetchone()
    )
    return int(row["n"])


RUN_A = "11111111-aaaa-4aaa-8aaa-000000000001"
RUN_B = "22222222-bbbb-4bbb-8bbb-000000000002"


def test_no_agent_done_and_task_in_progress_fails_the_run(client, tmp_path):
    tid = _task()
    seen = _spawn(client, tmp_path, RUN_A, tid)
    assert seen["claim"]["claimed"] is True
    assert seen["result"]["outcome"] == "failed"
    assert seen["result"]["error"] == "task_unfinished"

    synthetic = _last_agent_done(RUN_A)
    assert synthetic.get("synthetic") is True
    assert synthetic["outcome"] == "failed"
    assert synthetic["error"] == "task_unfinished"

    run = _detail(client, RUN_A)
    assert run["status"] == "error"
    assert run["outcome"] == "failed"
    assert run["error"] == "task_unfinished"

    row = _row(tid)
    assert row["task_status"] == "pending"
    assert row["claimed_by"] is None
    assert row["fail_reason"] == "task_unfinished"
    assert row["attempts"] == 1


@pytest.mark.parametrize("pty_first", [True, False], ids=["pty-first", "early-advance"])
def test_agents_own_success_is_reported_failed_with_one_invocation(
    client, tmp_path, pty_first
):
    tid = _task()
    seen = _spawn(
        client, tmp_path, RUN_A, tid, own_agent_done=True, pty_first=pty_first
    )
    # The spawn's own result says failed too, so the caller does not report success.
    assert seen["result"]["outcome"] == "failed"
    assert seen["result"]["error"] == "task_unfinished"

    # No second AGENT_DONE: the agent's own one is still the last, and still says success.
    own = _last_agent_done(RUN_A)
    assert own.get("synthetic") is not True
    assert own["outcome"] == "success"
    assert _invocation_rows(RUN_A) == 1

    run = _detail(client, RUN_A)
    assert run["outcome"] == "failed"
    assert run["error"] == "task_unfinished"
    assert run["status"] == "error"
    assert _row(tid)["task_status"] == "pending"


def test_the_freed_task_is_claimed_by_the_next_run(client, tmp_path):
    tid = _task()
    _spawn(client, tmp_path, RUN_A, tid)
    assert _row(tid)["task_status"] == "pending"

    seen = _spawn(client, tmp_path, RUN_B, tid, finish_task=True)
    assert seen["claim"]["claimed"] is True
    row = _row(tid)
    assert row["claimed_by"] == RUN_B
    assert row["attempts"] == 2
    assert row["task_status"] == "done"
    # A run whose task is done keeps success.
    assert _last_agent_done(RUN_B)["outcome"] == "success"
    run = _detail(client, RUN_B)
    assert run["status"] == "done"
    assert run["outcome"] == "success"


def test_at_the_attempt_limit_the_task_fails_and_escalates(client, tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    set_setting(get_db(), "goal.task_max_attempts", "2")
    tid = _task()
    dependent = _task("Build Y after X.", deps=[tid])

    _spawn(client, tmp_path, RUN_A, tid)
    assert _row(tid)["task_status"] == "pending"
    _spawn(client, tmp_path, RUN_B, tid)

    row = _row(tid)
    assert row["task_status"] == "failed"
    assert row["fail_reason"] == "task_unfinished"
    assert _row(dependent)["task_status"] == "blocked"
    escalations = (
        get_db()
        .execute(
            "SELECT text FROM comms_messages WHERE type='escalation' AND scope=?",
            (SCOPE,),
        )
        .fetchall()
    )
    assert len(escalations) == 1
    assert "task_unfinished" in escalations[0]["text"]
    assert _detail(client, RUN_B)["status"] == "error"


def test_a_run_whose_task_is_done_keeps_success(client, tmp_path):
    tid = _task()
    _spawn(client, tmp_path, RUN_A, tid, finish_task=True)

    synthetic = _last_agent_done(RUN_A)
    assert synthetic["outcome"] == "success"
    assert "error" not in synthetic
    run = _detail(client, RUN_A)
    assert run["status"] == "done"
    assert run["outcome"] == "success"
    assert _row(tid)["task_status"] == "done"


def _events_of(event_type: str, run_id: str) -> list:
    from pathly_orchestrator.db.connection import get_db

    rows = (
        get_db()
        .execute(
            "SELECT payload FROM fsm_events WHERE event_type=? ORDER BY seq",
            (event_type,),
        )
        .fetchall()
    )
    return [
        p for p in (json.loads(r["payload"]) for r in rows) if p.get("run_id") == run_id
    ]


def test_a_run_that_exits_nonzero_frees_its_task(client, tmp_path):
    """A crash, a rate limit after retries: the spawn raises, and the task is still freed
    (free only: no AGENT_DONE and no RUN_OUTCOME; run_history already says error)."""
    tid = _task()
    with pytest.raises(RuntimeError, match="terminal_exit_nonzero"):
        _spawn(client, tmp_path, RUN_A, tid, exit_code=1)

    row = _row(tid)
    assert row["task_status"] == "pending"
    assert row["claimed_by"] is None
    assert row["fail_reason"] == "task_unfinished"
    assert row["attempts"] == 1
    assert _events_of("AGENT_DONE", RUN_A) == []
    assert _events_of("RUN_OUTCOME", RUN_A) == []
    assert _detail(client, RUN_A)["status"] == "error"

    seen = _spawn(client, tmp_path, RUN_B, tid, finish_task=True)
    assert seen["claim"]["claimed"] is True
    assert _row(tid)["claimed_by"] == RUN_B


def test_early_advance_on_another_runs_agent_done_still_reports_failed(
    client, tmp_path
):
    """The feature's latest AGENT_DONE belongs to another run (and says failed): it is not
    this run's own report, so it must not stand in for one."""
    tid = _task()
    seen = _spawn(
        client,
        tmp_path,
        RUN_A,
        tid,
        own_agent_done=True,
        pty_first=False,
        agent_done_run_id=RUN_B,
        agent_done_outcome="failed",
    )
    assert seen["result"]["outcome"] == "failed"
    assert seen["result"]["error"] == "task_unfinished"
    run = _detail(client, RUN_A)
    assert run["outcome"] == "failed"
    assert run["error"] == "task_unfinished"
    assert run["status"] == "error"
    assert _row(tid)["task_status"] == "pending"
