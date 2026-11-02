"""chief-autopilot 08: a chief's runs are recorded, and the ended ones are listed for the person.

A call of a chief token that starts work (``chief_budget.STARTS_A_RUN`` and ``retry``) and is
answered 2xx with ``ok`` and a ``run_id`` records a ``chief_session_runs`` row; a 4xx records none,
and so does a 200 that says ``ok: false`` (a ``retry`` of a run that is still active names the old
run). ``GET /chief/notices?project_root=`` lists the project's recorded runs that reached a
terminal status and are unread, with what ``GET /runs/<id>`` says of them and the open questions
to the person on the run's board. ``POST /chief/notices/read`` marks them read; a chief token may
not call it. Every case runs the real gate and routes; what would start an agent is a stub.
"""

from __future__ import annotations

import sqlite3
from types import SimpleNamespace

import pytest
from chief_bind_support import _boards_are_free, feature_row, project_row, stubs
from chief_budget_support import flow_runs, retry, shown, start_flow
from chief_cite_support import db
from chief_gate_support import _chief, _gated, app, client, other_project, project


def recorded(chief=None) -> list[tuple[str, str, str]]:
    """``(session_run_id, run_id, project_root)`` of every recorded row (of one chief)."""
    rows = db().execute(
        "SELECT session_run_id, run_id, project_root FROM chief_session_runs"
        " ORDER BY started_at, run_id"
    )
    found = [tuple(r) for r in rows.fetchall()]
    if chief is None:
        return found
    return [r for r in found if r[0] == chief.run_id]


def finish(root, run_id: str, status: str, **outcome) -> None:
    """The run history says ``run_id`` is ``status``; an ``AGENT_DONE`` carries ``outcome``."""
    from pathly_orchestrator.db.queries.fsm_events import append_event
    from pathly_orchestrator.db.queries.run_history import upsert_run

    upsert_run(db(), str(root), "demo", run_id, status, board_scope="demo")
    if outcome:
        event = {"type": "AGENT_DONE", "run_id": run_id, **outcome}
        append_event(db(), str(root), "demo", event)


def cost(root, run_id: str, usd: float) -> None:
    conn = db()
    conn.execute(
        "INSERT INTO agent_invocations"
        " (project_root, feature, run_id, stage, started_at, tokens_in, tokens_out,"
        " cost_usd, board_scope) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(root),
            "demo",
            run_id,
            "BUILDING",
            "2026-11-01T00:00:00Z",
            10,
            0,
            usd,
            "demo",
        ),
    )
    conn.commit()


def notices(client, chief, root):
    resp = client.get(
        "/chief/notices",
        query_string={"project_root": str(root)},
        headers=chief.headers,
    )
    assert resp.status_code == 200, shown(resp)
    return resp.get_json()["notices"]


def mark_read(client, root, run_ids, headers=None):
    body = {"project_root": str(root), "run_ids": run_ids}
    return client.post("/chief/notices/read", json=body, headers=headers or {})


def goal_run(client, chief, project):
    body = {"goal_id": project_row(project, "goal"), "project_root": str(project)}
    return client.post("/comms/goals/run", json=body, headers=chief.headers)


# --- recording -------------------------------------------------------------------------------


def test_a_flow_start_records_the_run_for_the_chiefs_project(
    client, project, flow_runs
):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 200, shown(resp)
    assert recorded() == [(chief.run_id, "run-1", str(project))]


def test_a_goal_run_records_the_run(client, project, stubs):
    chief = _chief("operator", project)

    resp = goal_run(client, chief, project)

    assert resp.status_code == 200, shown(resp)
    assert recorded() == [(chief.run_id, "run-goal", str(project))]


def test_a_start_the_route_refuses_with_a_400_records_nothing(
    client, project, stubs, monkeypatch
):
    from pathly_orchestrator.supervisor import goal_run as goal_run_module

    def refused(goal_id, **kwargs):
        return {"ok": False, "reason": "unknown_executor", "run_id": "run-never"}

    monkeypatch.setattr(goal_run_module, "start_goal_run", refused)
    chief = _chief("operator", project)

    resp = goal_run(client, chief, project)

    assert resp.status_code == 400, shown(resp)
    assert recorded() == []


def test_a_flow_start_with_a_bad_body_records_nothing(client, project, flow_runs):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project, scope="")

    assert resp.status_code == 400, shown(resp)
    assert recorded() == []


def test_a_retry_that_answers_ok_false_records_nothing(client, project, flow_runs):
    """A retry of a run still active answers 200 ``ok: false`` with the OLD run id."""
    from pathly_orchestrator.supervisor import registry

    registry._registry["retry-topic"] = SimpleNamespace(
        run_id="run-own-1", status="running", project_root=str(project)
    )
    try:
        chief = _chief("operator", project)
        resp = retry(client, chief, project, max_cost_usd=1)
    finally:
        registry._registry.pop("retry-topic", None)

    assert resp.status_code == 200, shown(resp)
    assert resp.get_json()["ok"] is False
    assert recorded() == []


def test_a_call_without_a_chief_token_records_nothing(client, project, flow_runs):
    body = {
        "kind": "flow",
        "scope": "demo",
        "flow": "team",
        "project_root": str(project),
    }

    resp = client.post("/runs", json=body)

    assert resp.status_code == 200, shown(resp)
    assert recorded() == []


# --- the notices -----------------------------------------------------------------------------


def test_an_ended_run_is_listed_with_its_outcome_cost_and_questions(
    client, project, flow_runs
):
    chief = _chief("operator", project)
    start_flow(client, chief, project)
    start_flow(client, chief, project)
    finish(project, "run-1", "error", outcome="failed", error="waiting_for_answer")
    cost(project, "run-1", 0.25)
    finish(project, "run-2", "running")
    feature_row("demo", "question", to_agent="human")
    feature_row("demo", "escalation", to_agent="*")
    feature_row("demo", "question", to_agent="architect")
    feature_row("other", "question", to_agent="human")

    listed = notices(client, chief, project)

    assert [n["run_id"] for n in listed] == ["run-1"]
    notice = listed[0]
    assert notice["status"] == "error"
    assert notice["outcome"] == "failed"
    assert notice["error"] == "waiting_for_answer"
    assert notice["cost_usd"] == pytest.approx(0.25)
    assert notice["open_questions"] == 2
    assert notice["kind"] == "single"


def test_an_answered_question_is_not_counted(client, project, flow_runs):
    from pathly_orchestrator.db.queries.comms_messages import post_message

    chief = _chief("operator", project)
    start_flow(client, chief, project)
    finish(project, "run-1", "done", outcome="success")
    question = feature_row("demo", "question", to_agent="human")
    post_message(
        db(),
        board="feature",
        scope="demo",
        from_agent="human",
        type="answer",
        text="yes",
        reply_to=question,
    )

    (notice,) = notices(client, chief, project)

    assert notice["open_questions"] == 0
    assert notice["outcome"] == "success"


def test_marking_a_notice_read_hides_it(client, project, flow_runs):
    chief = _chief("operator", project)
    start_flow(client, chief, project)
    finish(project, "run-1", "done", outcome="success")

    resp = mark_read(client, project, ["run-1"])

    assert resp.status_code == 200, shown(resp)
    assert resp.get_json()["marked"] == 1
    assert notices(client, chief, project) == []


def test_a_chief_token_may_not_mark_notices_read(client, project, flow_runs):
    chief = _chief("operator", project)
    start_flow(client, chief, project)
    finish(project, "run-1", "done", outcome="success")

    resp = mark_read(client, project, ["run-1"], headers=chief.headers)

    assert resp.status_code == 403, shown(resp)
    assert _gated(resp)
    assert [n["run_id"] for n in notices(client, chief, project)] == ["run-1"]


def test_mark_read_needs_a_root_and_a_list_of_ids(client, project):
    bad_root = client.post("/chief/notices/read", json={"run_ids": ["x"]})
    bad_ids = mark_read(client, project, "run-1")

    assert bad_root.status_code == 400, shown(bad_root)
    assert bad_ids.status_code == 400, shown(bad_ids)


def test_another_projects_chief_sees_none_of_it(
    client, project, other_project, flow_runs
):
    chief = _chief("operator", project)
    start_flow(client, chief, project)
    finish(project, "run-1", "done", outcome="success")
    other = _chief("operator", other_project)

    own = notices(client, other, other_project)
    theirs = client.get(
        "/chief/notices",
        query_string={"project_root": str(project)},
        headers=other.headers,
    )

    assert own == []
    assert theirs.status_code == 403, shown(theirs)
    assert _gated(theirs)


def test_another_projects_mark_read_leaves_the_notice(
    client, project, other_project, flow_runs
):
    chief = _chief("operator", project)
    start_flow(client, chief, project)
    finish(project, "run-1", "done", outcome="success")

    mark_read(client, other_project, ["run-1"])

    assert [n["run_id"] for n in notices(client, chief, project)] == ["run-1"]


def test_the_notices_outlive_the_session(client, project, flow_runs):
    from pathly_orchestrator.db.queries import chief as sessions

    first = _chief("operator", project)
    start_flow(client, first, project)
    sessions.close_session(db(), first.run_id, "closed from Studio")
    finish(project, "run-1", "error", outcome="failed", error="task_unfinished")
    second = _chief("status", project)

    (notice,) = notices(client, second, project)

    assert notice["run_id"] == "run-1"
    assert notice["error"] == "task_unfinished"


def test_notices_need_a_project_root(client):
    resp = client.get("/chief/notices")

    assert resp.status_code == 400, shown(resp)


# --- the table -------------------------------------------------------------------------------


def test_the_migration_runs_twice_and_keeps_rows() -> None:
    from pathly_orchestrator.db.migrations_chief import add_chief_tables
    from pathly_orchestrator.db.queries.chief_session_runs import record_session_run

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    add_chief_tables(conn)
    record_session_run(conn, "chief-1", "run-1", "/p")
    add_chief_tables(conn)

    rows = conn.execute("SELECT session_run_id, run_id FROM chief_session_runs")
    assert [tuple(r) for r in rows.fetchall()] == [("chief-1", "run-1")]
