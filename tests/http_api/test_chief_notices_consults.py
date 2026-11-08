"""chief-autopilot-round-two 09: consult runs and routed questions in the run views and notices.

``GET /runs`` lists a ``consult-`` run as ``kind: consult``, and a loop parent's window cost leaves
out the invocations stamped ``category: consult`` (they are the consult's own row). ``GET
/runs/<id>`` carries the run's ``consults`` (the ``consult_routes`` rows asked by the run or its
children) and ``waiting_for_person`` (handed-on or withheld routes whose question has no answer).
``GET /chief/notices`` carries the same, takes a ``limit`` (1 to 200), and recording a chief's run
deletes the project's rows marked read more than 30 days ago.
"""

from __future__ import annotations

import time

import pytest
from chief_gate_support import _chief, _streams_do_not_block, app, client, project

LOOP_PARENT = "11111111-2222-3333-4444-555555555555"
SINGLE = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
CONSULT = "consult-0123456789ab"
LIMIT_ERROR = {"error": "limit must be an integer from 1 to 200"}


def db():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


def seed_run(root, run_id, adapter="claude", status="done", start="10:00", end="10:30"):
    from pathly_orchestrator.db.queries.run_history import upsert_run

    upsert_run(
        db(),
        str(root),
        "demo",
        run_id,
        status,
        started_at=f"2026-11-01T{start}:00+00:00",
        finished_at=f"2026-11-01T{end}:00+00:00" if end else None,
        adapter=adapter,
        board_scope="demo",
    )


def invocation(root, run_id, usd, at="10:10", category=None):
    conn = db()
    conn.execute(
        "INSERT INTO agent_invocations"
        " (project_root, feature, run_id, stage, started_at, tokens_in, tokens_out,"
        " cost_usd, board_scope, category) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            str(root),
            "demo",
            run_id,
            "BUILDING",
            f"2026-11-01T{at}:00+00:00",
            10,
            0,
            usd,
            "demo",
            category,
        ),
    )
    conn.commit()


def question(to_agent="architect") -> str:
    from pathly_orchestrator.db.queries.comms_messages import post_message

    return post_message(
        db(),
        board="feature",
        scope="demo",
        from_agent="builder",
        to_agent=to_agent,
        type="question",
        text="which way?",
    )


def answer(question_id: str) -> None:
    from pathly_orchestrator.db.queries.comms_messages import answer_question

    answer_question(db(), question_id, "this way")


def route(question_id, asking_run_id, status, role="architect", consult=None, why=None):
    conn = db()
    conn.execute(
        "INSERT INTO consult_routes (question_id, role, task_id, goal_key, asking_run_id,"
        " consult_run_id, status, reason, created_at, ended_at)"
        " VALUES (?, ?, NULL, NULL, ?, ?, ?, ?, ?, NULL)",
        (question_id, role, asking_run_id, consult, status, why, time.time()),
    )
    conn.commit()


def listed(client, root) -> dict:
    resp = client.get("/runs", query_string={"project_root": str(root)})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return {r["run_id"]: r for r in resp.get_json()}


def detail(client, run_id) -> dict:
    resp = client.get(f"/runs/{run_id}")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    return resp.get_json()["run"]


def single_with_two_routes(root) -> tuple[str, str]:
    """A single run whose architect question a consult answered and whose po question went on."""
    seed_run(root, SINGLE)
    answered = question("architect")
    route(answered, SINGLE, "answered", consult=CONSULT)
    answer(answered)
    handed = question("human")
    route(handed, SINGLE, "to_person", role="po", why="consult answered ANSWER: USER")
    return answered, handed


def notices(client, chief, root, **params):
    return client.get(
        "/chief/notices",
        query_string={"project_root": str(root), **params},
        headers=chief.headers,
    )


def test_runs_lists_a_consult_run_as_its_own_kind_and_out_of_the_loop_parents_cost(
    client, project
):
    seed_run(project, LOOP_PARENT, adapter="goal-loop")
    seed_run(project, "sched-T1#1", start="10:05", end="10:20")
    invocation(project, "sched-T1#1", 0.10, category="loop")
    seed_run(project, CONSULT, start="10:06", end="10:08")
    invocation(project, CONSULT, 0.40, at="10:07", category="consult")

    runs = listed(client, project)

    assert runs[CONSULT]["kind"] == "consult"
    assert runs[CONSULT]["cost_usd"] == pytest.approx(0.40)
    assert runs[LOOP_PARENT]["kind"] == "loop"
    assert runs[LOOP_PARENT]["cost_usd"] == pytest.approx(0.10)
    assert "sched-T1#1" not in runs
    assert detail(client, CONSULT)["kind"] == "consult"


def test_a_single_runs_detail_shows_its_consults_and_what_waits_for_the_person(
    client, project
):
    answered, handed = single_with_two_routes(project)
    other = question("tester")
    route(other, "another-run", "to_person", role="tester")

    run = detail(client, SINGLE)

    assert run["consults"] == [
        {
            "question_id": answered,
            "role": "architect",
            "status": "answered",
            "consult_run_id": CONSULT,
            "reason": None,
        },
        {
            "question_id": handed,
            "role": "po",
            "status": "to_person",
            "consult_run_id": None,
            "reason": "consult answered ANSWER: USER",
        },
    ]
    assert run["waiting_for_person"] == 1


def test_an_answered_hand_off_and_a_withheld_route_are_told_apart(client, project):
    seed_run(project, SINGLE)
    withheld = question("architect")
    route(withheld, SINGLE, "withheld", consult=CONSULT)
    handed = question("human")
    route(handed, SINGLE, "to_person", role="po")
    answer(handed)

    run = detail(client, SINGLE)

    assert [c["status"] for c in run["consults"]] == ["withheld", "to_person"]
    assert run["waiting_for_person"] == 1


def test_a_loop_parent_shows_its_tasks_consults(client, project):
    seed_run(project, LOOP_PARENT, adapter="goal-loop")
    seed_run(project, "sched-T1#1", start="10:05", end="10:20")
    seed_run(project, "sched-T2#1", start="10:06", end="10:21")
    first = question("architect")
    route(first, "sched-T1#1", "running", consult=CONSULT)
    second = question("human")
    route(second, "sched-T2#1", "to_person", role="designer")
    outside = question("tester")
    route(outside, "sched-T9#1", "to_person", role="tester")

    run = detail(client, LOOP_PARENT)

    assert [c["question_id"] for c in run["consults"]] == [first, second]
    assert run["waiting_for_person"] == 1


def test_a_run_without_routes_has_none(client, project):
    seed_run(project, SINGLE)

    run = detail(client, SINGLE)

    assert run["consults"] == []
    assert run["waiting_for_person"] == 0


def test_a_notice_carries_the_runs_consults(client, project):
    from pathly_orchestrator.db.queries.chief_session_runs import record_session_run

    chief = _chief("operator", project)
    answered, handed = single_with_two_routes(project)
    record_session_run(db(), chief.run_id, SINGLE, str(project))

    resp = notices(client, chief, project)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    [notice] = resp.get_json()["notices"]
    assert [c["question_id"] for c in notice["consults"]] == [answered, handed]
    assert notice["consults"] == detail(client, SINGLE)["consults"]
    assert notice["waiting_for_person"] == 1


def test_notices_take_a_limit(client, project):
    from pathly_orchestrator.db.queries.chief_session_runs import record_session_run

    chief = _chief("operator", project)
    for n in range(3):
        run_id = f"run-{n}"
        seed_run(project, run_id)
        record_session_run(
            db(), chief.run_id, run_id, str(project), started_at=100.0 + n
        )

    two = notices(client, chief, project, limit="2")
    every = notices(client, chief, project)

    assert two.status_code == 200, two.get_data(as_text=True)
    assert [n["run_id"] for n in two.get_json()["notices"]] == ["run-0", "run-1"]
    assert len(every.get_json()["notices"]) == 3
    for bad in ("0", "x", "201", "-1", "2.5"):
        resp = notices(client, chief, project, limit=bad)
        assert resp.status_code == 400, bad
        assert resp.get_json() == LIMIT_ERROR
    assert notices(client, chief, project, limit="200").status_code == 200


def test_recording_a_run_deletes_the_projects_rows_read_over_30_days_ago(project):
    from pathly_orchestrator.db.queries.chief_session_runs import record_session_run

    conn = db()
    for run_id, root in (
        ("old-read", project),
        ("recent-read", project),
        ("old-unread", project),
        ("old-other", "/elsewhere"),
    ):
        record_session_run(conn, "chief-aaaaaaaaaaaa", run_id, str(root))
    now = time.time()
    for run_id, read_at in (
        ("old-read", now - 31 * 86400),
        ("recent-read", now - 86400),
        ("old-other", now - 31 * 86400),
    ):
        conn.execute(
            "UPDATE chief_session_runs SET read_at = ? WHERE run_id = ?",
            (read_at, run_id),
        )
    conn.commit()

    record_session_run(conn, "chief-aaaaaaaaaaaa", "next", str(project))

    kept = {
        r[0] for r in conn.execute("SELECT run_id FROM chief_session_runs").fetchall()
    }
    assert kept == {"recent-read", "old-unread", "old-other", "next"}
