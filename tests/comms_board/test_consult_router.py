"""chief-autopilot-round-two 04: a run's role question is routed to a consult when it is posted.

``supervisor/consult_router.on_question`` acts on one posted question: ``route_decision`` says
``none`` (nothing), ``person`` (``hand_to_person``) or ``route``; a route with no spawn host
listening leaves the question as posted (``no_host``), else ``record_route`` and ``start`` on a
daemon thread named ``consult-<question id prefix>``. ``http_server/consult_trigger.py`` is the
``after_request`` hook on ``POST /comms/post`` that calls it for a ``question`` answered 200 with
``ok`` and a ``message_id``. ``app.main`` hands every ``queued`` or ``running`` route to the person
at start (``end_stale_routes``).

Every test injects a fake ``start`` (no consult is spawned) and waits for the router's thread.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
from contextlib import closing
from pathlib import Path

import pytest
from _paths import SRC
from chief_acceptance_support import (
    TOKEN_HEADER,
    _no_embedding_model,
    _no_watcher_outlives_its_test,
    client,
    db,
    project,
    spawn_host,
)

from pathly_orchestrator.db.queries import consult_routes as cr
from pathly_orchestrator.db.queries.app_settings import set_setting
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.run_tokens import mint_run_token

SCOPE = "demo"
ROUTER_THREAD = "consult-"


class FakeStart:
    """Stands in for ``consult_run.start_consult``: records each call, starts nothing."""

    def __init__(self, result: dict | None = None, raises: Exception | None = None):
        self.calls: list[dict] = []
        self.result = result
        self.raises = raises

    def __call__(self, question_id, *, project_root, broadcast_fn, block):
        self.calls.append(
            {
                "question_id": question_id,
                "project_root": project_root,
                "broadcast_fn": broadcast_fn,
                "block": block,
                "thread": threading.current_thread().name,
            }
        )
        if self.raises is not None:
            raise self.raises
        if self.result is not None:
            return self.result
        return {
            "started": True,
            "run_id": "consult-0123456789ab",
            "role": "architect",
            "status": "running",
        }


def _join_router_threads() -> None:
    for thread in threading.enumerate():
        if thread.name.startswith(ROUTER_THREAD) and thread.is_alive():
            thread.join(timeout=10)
    alive = [
        t.name
        for t in threading.enumerate()
        if t.name.startswith(ROUTER_THREAD) and t.is_alive()
    ]
    assert alive == [], f"router threads outlived the test: {alive}"


@pytest.fixture(autouse=True)
def _router_threads_end():
    yield
    _join_router_threads()


@pytest.fixture()
def fake_start(monkeypatch) -> FakeStart:
    from pathly_orchestrator.supervisor import consult_router

    start = FakeStart()
    monkeypatch.setattr(consult_router, "start_consult", start)
    return start


def _task(goal_id: str | None = "goal-1") -> str:
    return post_message(
        db(), "feature", SCOPE, "planner", type="task", text="build it", goal_id=goal_id
    )


def _token(run_id: str, root: Path | None, scope: str = SCOPE) -> dict:
    token = mint_run_token(
        db(), run_id, "builder", scope, str(root) if root else None, "feature", scope
    )
    return {TOKEN_HEADER: token}


def _body(to: str, root: Path | None, text: str = "Which store?", **extra) -> dict:
    body = {
        "feature": SCOPE,
        "board": "feature",
        "scope": SCOPE,
        "from": "builder",
        "to": to,
        "type": "question",
        "text": text,
        **extra,
    }
    if root is not None:
        body["project_root"] = str(root)
    return body


def _ask(
    client, to: str, root: Path | None, headers: dict | None = None, **extra
) -> str:
    body = _body(to, root, **extra)
    resp = client.post("/comms/post", json=body, headers=headers or {})
    assert resp.status_code == 200, resp.get_data(as_text=True)
    _join_router_threads()
    return resp.get_json()["message_id"]


def _to_agent(qid: str) -> str:
    row = db().execute("SELECT to_agent FROM comms_messages WHERE id=?", (qid,))
    return row.fetchone()["to_agent"]


def _routes(qid: str) -> list[dict]:
    return cr.routes_for_questions(db(), [qid])


def _status_replies(qid: str) -> list[str]:
    rows = db().execute(
        "SELECT text FROM comms_messages WHERE reply_to=? AND type='status'", (qid,)
    )
    return [r["text"] for r in rows.fetchall()]


# ── through POST /comms/post ─────────────────────────────────────────────────


def test_a_question_to_architect_records_one_route_and_starts_once(
    client, project, spawn_host, fake_start
):
    from pathly_orchestrator.http_server import sse

    tid = _task()
    qid = _ask(client, "architect", project, _token(f"sched-{tid}#1", project))

    routes = _routes(qid)
    assert len(routes) == 1
    assert routes[0]["status"] == "queued"
    assert routes[0]["role"] == "architect"
    assert routes[0]["task_id"] == tid
    assert len(fake_start.calls) == 1
    call = fake_start.calls[0]
    assert call["question_id"] == qid
    assert call["project_root"] == str(project)
    assert call["broadcast_fn"] is sse._broadcast_spawn
    assert call["block"] is False
    assert call["thread"] == f"consult-{qid[:8]}"
    assert _to_agent(qid) == "architect"


def test_a_question_with_no_root_in_the_body_starts_with_the_tokens_root(
    client, project, spawn_host, fake_start
):
    tid = _task()
    qid = _ask(client, "architect", None, _token(f"sched-{tid}#1", project))
    assert [c["project_root"] for c in fake_start.calls] == [str(project)]
    assert _routes(qid)[0]["status"] == "queued"


def test_a_question_naming_another_root_starts_with_the_tokens_root(
    client, project, spawn_host, fake_start, tmp_path
):
    elsewhere = tmp_path / "another-project"
    elsewhere.mkdir()
    tid = _task()
    qid = _ask(client, "architect", elsewhere, _token(f"sched-{tid}#1", project))
    assert [c["project_root"] for c in fake_start.calls] == [str(project)]
    assert _routes(qid)[0]["status"] == "queued"


def test_a_token_with_no_root_hands_the_question_to_the_person(
    client, project, spawn_host, fake_start
):
    tid = _task()
    qid = _ask(client, "architect", project, _token(f"sched-{tid}#1", None))
    assert fake_start.calls == []
    assert _to_agent(qid) == "human"
    route = _routes(qid)[0]
    assert route["status"] == "to_person"
    assert route["reason"] == "the asking run's token names no project root"


def test_a_question_on_another_board_than_the_tokens_goes_to_the_person(
    client, project, spawn_host, fake_start
):
    tid = _task()
    qid = _ask(
        client,
        "architect",
        project,
        _token(f"sched-{tid}#1", project),
        scope="other-feature",
    )
    assert fake_start.calls == []
    assert _to_agent(qid) == "human"
    route = _routes(qid)[0]
    assert route["status"] == "to_person"
    assert route["reason"] == (
        "the question is on board feature/other-feature, "
        "the asking run's is feature/demo"
    )


def test_the_hook_twice_for_one_message_starts_once(
    client, project, spawn_host, fake_start
):
    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.http_server.consult_trigger import trigger_consult

    tid = _task()
    headers = _token(f"sched-{tid}#1", project)
    qid = _ask(client, "architect", project, headers)
    assert len(fake_start.calls) == 1

    with app.test_request_context(
        "/comms/post", method="POST", json=_body("architect", project), headers=headers
    ):
        again = app.response_class(
            json.dumps({"ok": True, "message_id": qid}),
            status=200,
            mimetype="application/json",
        )
        assert trigger_consult(again) is again
    _join_router_threads()

    assert len(fake_start.calls) == 1
    assert len(_routes(qid)) == 1


def test_a_question_to_the_person_routes_nothing(
    client, project, spawn_host, fake_start
):
    tid = _task()
    qid = _ask(client, "human", project, _token(f"sched-{tid}#1", project))
    assert fake_start.calls == []
    assert _routes(qid) == []
    assert _to_agent(qid) == "human"


def test_a_tokenless_question_routes_nothing(client, project, spawn_host, fake_start):
    qid = _ask(client, "architect", project)
    assert fake_start.calls == []
    assert _routes(qid) == []
    assert _to_agent(qid) == "architect"


def test_a_question_to_builder_goes_to_the_person(
    client, project, spawn_host, fake_start
):
    tid = _task()
    qid = _ask(client, "builder", project, _token(f"sched-{tid}#1", project))
    assert fake_start.calls == []
    assert _to_agent(qid) == "human"
    routes = _routes(qid)
    assert [r["status"] for r in routes] == ["to_person"]
    assert routes[0]["reason"] == "unknown role builder"
    assert _status_replies(qid) == [
        "pathly handed this question to the person: unknown role builder"
    ]


def test_the_fourth_role_question_of_a_task_goes_to_the_person(
    client, project, spawn_host, fake_start
):
    tid = _task()
    headers = _token(f"sched-{tid}#1", project)
    first = [_ask(client, "architect", project, headers) for _ in range(3)]
    assert len(fake_start.calls) == 3
    assert all(_routes(q)[0]["status"] == "queued" for q in first)

    fourth = _ask(client, "architect", project, headers)
    assert len(fake_start.calls) == 3
    assert _to_agent(fourth) == "human"
    route = _routes(fourth)[0]
    assert route["status"] == "to_person"
    assert route["reason"] == f"routed question limit (3) reached for task {tid}"


def test_a_goal_at_its_cost_line_routes_nothing_new(
    client, project, spawn_host, fake_start
):
    conn = db()
    tid = _task(goal_id="goal-9")
    run = f"sched-{tid}#1"
    earlier = post_message(
        conn,
        "feature",
        SCOPE,
        "builder",
        to_agent="architect",
        type="question",
        text="earlier",
        author_role="builder",
        author_run_id=run,
        author_source="token",
    )
    decision = cr.route_decision(conn, earlier)
    assert cr.record_route(conn, decision, earlier, status="answered")
    cr.set_route_status(
        conn, earlier, "answered", consult_run_id="consult-aaaaaaaaaaaa"
    )
    conn.execute(
        "INSERT INTO agent_invocations (project_root, feature, run_id, cost_usd) "
        "VALUES (?, ?, ?, ?)",
        (str(project), SCOPE, "consult-aaaaaaaaaaaa", 2.0),
    )
    conn.commit()

    qid = _ask(client, "architect", project, _token(run, project))
    assert fake_start.calls == []
    assert _to_agent(qid) == "human"
    assert [r["status"] for r in _routes(qid)] == ["to_person"]
    assert _routes(qid)[0]["reason"] == "consult cost line $2.00 reached for goal-9"


def test_no_spawn_host_leaves_the_question_as_posted(client, project, fake_start):
    from pathly_orchestrator.http_server import sse
    from pathly_orchestrator.supervisor.consult_router import on_question

    assert sse._spawn_clients == []
    tid = _task()
    qid = _ask(client, "architect", project, _token(f"sched-{tid}#1", project))
    assert fake_start.calls == []
    assert _routes(qid) == []
    assert _to_agent(qid) == "architect"
    assert _status_replies(qid) == []

    said = on_question(
        qid,
        project_root=str(project),
        board="feature",
        scope=SCOPE,
        broadcast_fn=sse._broadcast_spawn,
        host_present=False,
    )
    assert said == "no_host"
    assert fake_start.calls == []
    assert _routes(qid) == []
    assert _to_agent(qid) == "architect"


def test_a_post_that_is_not_a_question_starts_nothing(
    client, project, spawn_host, fake_start
):
    tid = _task()
    body = {**_body("architect", project), "type": "status"}
    resp = client.post(
        "/comms/post", json=body, headers=_token(f"sched-{tid}#1", project)
    )
    assert resp.status_code == 200
    _join_router_threads()
    assert fake_start.calls == []
    assert _routes(resp.get_json()["message_id"]) == []


# ── on_question directly ─────────────────────────────────────────────────────


def _question(run_id: str, to: str = "architect") -> str:
    return post_message(
        db(),
        "feature",
        SCOPE,
        "builder",
        to_agent=to,
        type="question",
        text="?",
        author_role="builder",
        author_run_id=run_id,
        author_source="token",
    )


def _on(qid: str, start) -> str:
    from pathly_orchestrator.supervisor.consult_router import on_question

    said = on_question(
        qid,
        project_root="/p",
        board="feature",
        scope=SCOPE,
        broadcast_fn=None,
        host_present=True,
        start=start,
    )
    _join_router_threads()
    return said


def test_on_question_says_what_it_did():
    start = FakeStart()
    tid = _task()
    run = f"sched-{tid}#1"
    assert _on(_question(run), start) == "routed"
    assert _on(_question(run, to="human"), start) == "none"
    assert _on(_question(run, to="builder"), start) == "person"
    assert len(start.calls) == 1


def test_a_start_that_raises_hands_the_question_on_and_fails_the_route():
    start = FakeStart(raises=RuntimeError("no adapter"))
    tid = _task()
    qid = _question(f"sched-{tid}#1")
    assert _on(qid, start) == "routed"
    assert len(start.calls) == 1
    route = _routes(qid)[0]
    assert route["status"] == "failed"
    assert "RuntimeError: no adapter" in route["reason"]
    assert _to_agent(qid) == "human"
    replies = _status_replies(qid)
    assert len(replies) == 1 and "RuntimeError: no adapter" in replies[0]


def test_a_start_that_does_not_start_a_queued_route_hands_it_on():
    start = FakeStart(result={"started": False, "reason": "not a live question"})
    tid = _task()
    qid = _question(f"sched-{tid}#1")
    assert _on(qid, start) == "routed"
    route = _routes(qid)[0]
    assert route["status"] == "failed"
    assert "not a live question" in route["reason"]
    assert _to_agent(qid) == "human"


def test_a_start_that_lost_the_route_to_another_leaves_it():
    tid = _task()
    qid = _question(f"sched-{tid}#1")

    def claimed_elsewhere(question_id, **_kw):
        cr.set_route_status(db(), question_id, "running", consult_run_id="consult-x")
        return {"started": False, "reason": "another start claimed the route"}

    assert _on(qid, claimed_elsewhere) == "routed"
    route = _routes(qid)[0]
    assert route["status"] == "running"
    assert _to_agent(qid) == "architect"
    assert _status_replies(qid) == []


def test_a_lost_insert_asks_route_decision_again(monkeypatch):
    """``record_route`` False (a racing question took the last slot): the question goes to the
    person with the limit reason, and nothing starts."""
    set_setting(db(), "consult.max_per_task", "1")
    tid = _task()
    run = f"sched-{tid}#1"
    racer, qid = _question(run), _question(run)
    real = cr.record_route

    def racing(conn, decision, question_id, status="queued"):
        if question_id == qid:
            real(conn, cr.route_decision(conn, racer), racer)
        return real(conn, decision, question_id, status)

    monkeypatch.setattr(cr, "record_route", racing)
    start = FakeStart()
    assert _on(qid, start) == "person"
    monkeypatch.setattr(cr, "record_route", real)
    assert start.calls == []
    assert _to_agent(qid) == "human"
    assert _routes(qid)[0]["status"] == "to_person"


# ── app.main hands stale routes to the person ────────────────────────────────

MAIN_SCRIPT = """
import importlib, json, sys
app_module = importlib.import_module("pathly_orchestrator.http_server.app")
import pathly_orchestrator.runner.embeddings as embeddings
from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import consult_routes as cr
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.supervisor import chief_session

embeddings.warm = lambda: None
app_module.app.run = lambda *a, **k: None
conn = get_db()
qid = post_message(
    conn, "feature", "demo", "builder", to_agent="architect", type="question", text="?",
    author_role="builder", author_run_id="run-1", author_source="token",
)
cr.record_route(conn, cr.route_decision(conn, qid), qid)
cr.set_route_status(conn, qid, "running", consult_run_id="consult-0123456789ab")
if sys.argv[1] == "fail":
    def explode():
        raise RuntimeError("cleanup exploded")
    chief_session.chief_startup_cleanup = explode
app_module.main()
route = cr.routes_for_questions(conn, [qid])[0]
row = conn.execute("SELECT to_agent FROM comms_messages WHERE id=?", (qid,)).fetchone()
print(json.dumps({"qid": qid, "status": route["status"], "reason": route["reason"],
                  "to": row["to_agent"]}))
"""


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_main(tmp_path: Path, mode: str) -> tuple[dict, str]:
    home = tmp_path / "main-home"
    home.mkdir()
    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "PYTHONPATH": str(SRC),
        "PATHLY_FSM_HTTP_PORT": str(_free_port()),
    }
    done = subprocess.run(
        [sys.executable, "-c", MAIN_SCRIPT, mode],
        env=env,
        cwd=str(tmp_path),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout.strip().splitlines()[-1]), done.stderr


@pytest.mark.parametrize("mode", ["ok", "fail"])
def test_main_hands_a_running_route_to_the_person_at_start(tmp_path, mode):
    report, stderr = _run_main(tmp_path, mode)
    assert report["status"] == "to_person"
    assert report["reason"] == "server restart"
    assert report["to"] == "human"
    assert report["qid"] in stderr
