"""chief-autopilot-round-two 19: a server-routed consult starts for real, on the asking run's
board, and is billed once.

Found by the acceptance ticket (12), driving the real routes end to end:

1. ``http_server/consult_trigger.py`` hands ``on_question`` the spawn broadcaster the stage spawn
   calls as ``broadcast_fn(topic, payload)`` (``sse._broadcast_runner``): a role question posted
   with a live run token, with a spawn host listening, reaches a ``TERMINAL_SPAWN`` for a
   ``consult-`` run and the route is not ``failed``.
2. The ``consult`` fragment's post names ``"board": "<board>"``, so a question posted as the
   fragment says, on the project board with a single run's ``project`` token, is routed (not
   handed to the person); and a ``goal-loop`` flow run that ``goal_executor`` starts for a goal on
   the project board has ``scope_tier == "project"`` (its ``sched-`` task tokens are minted with
   it).
3. A project-board run's own ``AGENT_DONE`` is found (the project root is derived by the
   ``pathly/`` anchor), so a consult on the project board whose agent wrote its ``AGENT_DONE``
   leaves exactly one ``agent_invocations`` row.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from pathlib import Path

import pytest
from _paths import SRC

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries import consult_routes as cr
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.comms_tasks import claim_task
from pathly_orchestrator.db.queries.run_tokens import mint_run_token
from pathly_orchestrator.db.queries.task_waits import park_task
from pathly_orchestrator.supervisor import consult_run
from pathly_orchestrator.supervisor.registry import get_run

TOKEN_HEADER = "X-Pathly-Run-Token"
FEATURE = "demo"
QUESTION = "Should the parser stream the rows or read the whole file?"
FRAGMENT = SRC / "pathly_data" / "core" / "skills" / "fragments" / "consult.md"
CONSULT_PREFIX = "consult-"
WAIT = 30.0


def _wait_for(condition, what: str, timeout: float = WAIT):
    deadline = time.monotonic() + timeout
    while True:
        found = condition()
        if found:
            return found
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.02)


def _consult_threads() -> list[threading.Thread]:
    return [
        t
        for t in threading.enumerate()
        if t.is_alive() and t.name.startswith(CONSULT_PREFIX)
    ]


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)
    monkeypatch.setattr(_emb, "embed", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _consults_end():
    """Every consult thread (the router's and the run's) ends inside its test."""
    yield
    _wait_for(lambda: not _consult_threads(), "the consult threads to end")


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    (root / "pathly" / "features" / FEATURE).mkdir(parents=True)
    (root / "pathly" / "project").mkdir(parents=True)
    return root


class Host:
    """A spawn host on ``/events/spawn`` (a queue in ``sse._spawn_clients``): for every
    ``TERMINAL_SPAWN`` of a ``consult-`` run it writes that run's ``AGENT_DONE`` (the agent's own)
    into ``storage``, then reports the PTY started and finished."""

    def __init__(self, storage: Path) -> None:
        self.storage = storage
        self.inbox: queue.Queue = queue.Queue()
        self.spawns: list[dict] = []
        self.errors: list[BaseException] = []
        self._thread = threading.Thread(target=self._loop, name="fake-host-19")

    def __enter__(self) -> "Host":
        from pathly_orchestrator.http_server import sse

        with sse._spawn_lock:
            sse._spawn_clients.append(self.inbox)
        self._thread.start()
        return self

    def __exit__(self, *exc) -> None:
        from pathly_orchestrator.http_server import sse

        _wait_for(lambda: not _consult_threads(), "the consult threads to end")
        with sse._spawn_lock:
            if self.inbox in sse._spawn_clients:
                sse._spawn_clients.remove(self.inbox)
        self.inbox.put(None)
        self._thread.join(timeout=WAIT)
        assert self.errors == [], self.errors

    def _loop(self) -> None:
        while True:
            raw = self.inbox.get()
            if raw is None:
                return
            try:
                self._handle(json.loads(raw))
            except BaseException as exc:  # reported on exit, never swallowed
                self.errors.append(exc)

    def _handle(self, payload: dict) -> None:
        from pathly_orchestrator.eventlog import append_event

        if payload.get("type") != "TERMINAL_SPAWN":
            return
        run_id = payload["run_id"]
        if not run_id.startswith(CONSULT_PREFIX):
            return
        self.spawns.append(payload)
        append_event(
            str(self.storage),
            {
                "type": "AGENT_DONE",
                "agent": "architect",
                "run_id": run_id,
                "category": "consult",
                "outcome": "success",
                "summary": "ANSWER: Stream the rows.",
                "cost_usd": 0.0,
            },
        )
        run = get_run(run_id)
        assert run is not None, run_id
        run.mark_started()
        run.mark_pty_result(
            {
                "result": {"cost_usd": 0.42, "tokens_in": 1200, "tokens_out": 300},
                "exit_code": 0,
            }
        )


def _route(question_id: str) -> dict | None:
    routes = cr.routes_for_questions(get_db(), [question_id])
    return routes[0] if routes else None


def _ended_route(question_id: str) -> dict:
    def ended():
        route = _route(question_id)
        return route if route and route["status"] in cr.END_STATUSES else None

    return _wait_for(ended, f"the route of {question_id} to end")


def _to_agent(question_id: str) -> str:
    row = get_db().execute(
        "SELECT to_agent FROM comms_messages WHERE id=?", (question_id,)
    )
    return row.fetchone()["to_agent"]


def _fragment_post(board: str, feature: str) -> dict:
    """The body of the ``consult`` fragment's post, its placeholders filled as a prompt has them."""
    text = FRAGMENT.read_text(encoding="utf-8")
    found = re.search(r"POST [^\n]*/comms/post\n(\{.*?\})\n```", text, re.S)
    assert found, "the consult fragment's /comms/post block"
    body = found.group(1)
    for marker, value in (
        ("<board>", board),
        ("<feature>", feature),
        ("<your role>", "builder"),
        ("<role>", "architect"),
    ):
        body = body.replace(marker, value)
    data = json.loads(body)
    data["text"] = QUESTION
    return data


# -- 1. the consult spawn reaches a host --------------------------------------------------------


def test_a_routed_question_reaches_a_terminal_spawn_for_a_consult_run(client, project):
    conn = get_db()
    tid = post_message(conn, "feature", FEATURE, "planner", type="task", text="Parse.")
    run_id = f"sched-{tid}#1"
    assert claim_task(conn, tid, run_id)
    token = mint_run_token(
        conn, run_id, "builder", FEATURE, str(project), "feature", FEATURE
    )
    body = _fragment_post("feature", FEATURE)

    with Host(project / "pathly" / "features" / FEATURE) as host:
        resp = client.post("/comms/post", json=body, headers={TOKEN_HEADER: token})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        question = resp.get_json()["message_id"]
        route = _ended_route(question)

    assert route["status"] != "failed", route
    assert route["status"] == "answered", route
    assert len(host.spawns) == 1
    assert host.spawns[0]["run_id"].startswith(CONSULT_PREFIX)
    assert route["consult_run_id"] == host.spawns[0]["run_id"]


# -- 2. the question is on the asking run's board -----------------------------------------------


def test_the_consult_fragment_posts_on_the_runs_board():
    text = FRAGMENT.read_text(encoding="utf-8")
    post = re.search(r"POST [^\n]*/comms/post\n(\{.*?\})\n```", text, re.S)
    assert post and '"board": "<board>"' in post.group(1)


@pytest.mark.parametrize("skill", ["team/build", "team/review", "team/test"])
def test_the_composed_team_prompts_post_the_consult_on_the_stage_board(skill):
    from pathly_orchestrator.fsm_compose import _inject_prompt_vars
    from pathly_orchestrator.skills.compose import compose_skill

    body = _inject_prompt_vars(
        compose_skill(skill, "claude"),
        feature=FEATURE,
        project_root="/x",
        agent_role="builder",
        storage_path=Path("/x/pathly/features") / FEATURE,
        skill=skill,
        board_tier="project",
        run_category="flow",
    )
    section = body[body.index("**To consult, post a board question") :]
    post = section[: section.index("```", section.index("{"))]
    assert '"board": "project"' in post


def test_a_single_runs_question_posted_as_the_fragment_says_is_routed(
    client, project, monkeypatch
):
    from pathly_orchestrator.http_server import sse
    from pathly_orchestrator.supervisor import consult_router

    started: list[str] = []

    def fake_start(question_id, *, project_root, broadcast_fn, block):
        started.append(question_id)
        return {"started": True, "run_id": "consult-0123456789ab", "status": "running"}

    monkeypatch.setattr(consult_router, "start_consult", fake_start)
    root = str(project)
    conn = get_db()
    run_id = "0b1c2d3e-single-run"
    token = mint_run_token(conn, run_id, "builder", root, root, "project", root)
    inbox: queue.Queue = queue.Queue()
    with sse._spawn_lock:
        sse._spawn_clients.append(inbox)
    try:
        resp = client.post(
            "/comms/post",
            json=_fragment_post("project", root),
            headers={TOKEN_HEADER: token},
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        question = resp.get_json()["message_id"]
        _wait_for(lambda: started, "the consult to start")
    finally:
        with sse._spawn_lock:
            sse._spawn_clients.remove(inbox)

    assert started == [question]
    assert _route(question)["status"] == "queued"
    assert _to_agent(question) == "architect"


@pytest.fixture()
def goal_runs(project, monkeypatch):
    """Start goal flow runs for real (``goal_executor`` -> ``api.start_run``) with the FSM loop
    stubbed (``park`` set: the loop parks the run, as a human checkpoint does), and take every
    run the test started out of the runner registry afterwards."""
    from pathly_orchestrator.supervisor import base_smoke, orchestrator, registry
    from pathly_orchestrator.supervisor.goal_executor import start_goal_run

    park: list[bool] = []

    def loop(state, broadcast_fn):
        if park:
            state.status = "parked"

    monkeypatch.setattr(orchestrator, "_loop", loop)
    monkeypatch.setattr(base_smoke, "check_base", lambda state, broadcast_fn: True)
    started: list = []

    def start(executor: str):
        root = str(project)
        goal = post_message(
            get_db(), "project", root, "chief", type="goal", text="Ship the parser"
        )
        done: list = []
        result = start_goal_run(
            goal,
            executor_override=executor,
            project_root=root,
            on_done=lambda *a: done.append(a),
        )
        assert result["ok"], result
        _wait_for(lambda: done, "the run to end")
        state = next(
            s for s in registry._registry.values() if s.run_id == result["run_id"]
        )
        started.append(state.topic)
        return goal, state

    start.park = park  # type: ignore[attr-defined]
    start.started = started  # type: ignore[attr-defined]
    yield start
    with registry._lock:
        for topic in started:
            registry._registry.pop(topic, None)


def test_a_goal_loop_run_on_the_project_board_has_the_project_scope_tier(goal_runs):
    _, state = goal_runs("loop")

    assert state.flow == "goal-loop"
    assert state.scope_tier == "project"


def test_a_resumed_goal_loop_run_keeps_the_project_scope_tier(goal_runs):
    from pathly_orchestrator.supervisor import registry
    from pathly_orchestrator.supervisor.api import resume_parked_run

    goal_runs.park.append(True)
    _, parked = goal_runs("loop")
    assert (parked.status, parked.scope_tier) == ("parked", "project")
    goal_runs.park.clear()

    done: list = []
    resumed = resume_parked_run(parked.topic, on_done=lambda *a: done.append(a))

    _wait_for(lambda: done, "the resumed run to end")
    assert resumed.run_id != parked.run_id
    assert registry._registry[parked.topic] is resumed
    assert resumed.scope_tier == "project"


def test_a_team_build_stage_question_on_the_project_board_is_routed(
    client, project, goal_runs, monkeypatch
):
    """The real stage path of a project-board team-build goal: the stage prompt from
    ``fsm_compose.build_prompt`` and the token ``_mint_spawn_token`` mints for its spawn. The
    consult post the prompt gives, sent with that token, is routed (not handed to the person):
    the prompt's board and the token's board come from one place."""
    from pathly_orchestrator.fsm_compose import build_prompt
    from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path
    from pathly_orchestrator.http_server import sse
    from pathly_orchestrator.supervisor import consult_router
    from pathly_orchestrator.supervisor.terminal_identity import (
        _mint_spawn_token,
        _run_board_scope,
    )

    started: list[str] = []

    def fake_start(question_id, *, project_root, broadcast_fn, block):
        started.append(question_id)
        return {"started": True, "run_id": "consult-0123456789ab", "status": "running"}

    monkeypatch.setattr(consult_router, "start_consult", fake_start)
    root = str(project)
    goal, state = goal_runs("team")
    assert state.flow == "team-build"
    storage = Path(_resolve_storage_path(None, root, state.topic))
    prompt = build_prompt(
        _load_flow("team-build", root), "BUILDING", storage, goal_id=goal
    )
    section = prompt[prompt.index("**To consult, post a board question") :]
    found = re.search(r"POST [^\n]*/comms/post\n(\{.*?\})\n```", section, re.S)
    assert found, "the stage prompt's consult post"
    body = json.loads(
        found.group(1).replace("<your role>", "builder").replace("<role>", "architect")
    )
    body["text"] = QUESTION
    tid = post_message(
        get_db(), "project", root, "planner", type="task", text="Parse.", goal_id=goal
    )
    run_id = f"{state.run_id}-build"
    assert claim_task(get_db(), tid, run_id)
    token = _mint_spawn_token(
        state, run_id, "builder", storage.name, _run_board_scope(state, storage)
    )
    assert token
    inbox: queue.Queue = queue.Queue()
    with sse._spawn_lock:
        sse._spawn_clients.append(inbox)
    try:
        resp = client.post("/comms/post", json=body, headers={TOKEN_HEADER: token})
        assert resp.status_code == 200, resp.get_data(as_text=True)
        question = resp.get_json()["message_id"]
        _wait_for(lambda: started or _to_agent(question) == "human", "the routing")
    finally:
        with sse._spawn_lock:
            sse._spawn_clients.remove(inbox)

    assert _to_agent(question) == "architect"
    assert started == [question]
    assert _route(question)["status"] == "queued"


# -- 3. a project-board consult is billed once --------------------------------------------------


def test_a_project_board_consult_with_its_own_agent_done_leaves_one_invocation(
    project, monkeypatch
):
    monkeypatch.setenv("PATHLY_RUNNER_EARLY_ADVANCE", "0")
    root = str(project)
    conn = get_db()
    tid = post_message(conn, "project", root, "planner", type="task", text="Parse.")
    run_id = f"sched-{tid}#1"
    assert claim_task(conn, tid, run_id)
    question = post_message(
        conn,
        "project",
        root,
        "builder",
        to_agent="architect",
        type="question",
        text=QUESTION,
        author_role="builder",
        author_run_id=run_id,
        author_source="token",
    )
    decision = cr.route_decision(conn, question)
    assert decision.kind == "route", decision
    assert cr.record_route(conn, decision, question)
    assert park_task(conn, tid, [question])
    storage = project / "pathly" / "project"
    host = Host(storage)

    def spawn(**kwargs) -> dict:
        def broadcast(_topic, payload):
            host._handle(payload)

        kwargs["broadcast_fn"] = broadcast
        return consult_run._default_spawn(**kwargs)

    result = consult_run.start_consult(
        question, project_root=root, broadcast_fn=None, spawn_fn=spawn, block=True
    )

    assert host.spawns, "the consult spawned"
    consult = result["run_id"]
    rows = (
        get_db()
        .execute(
            "SELECT agent_role, category FROM agent_invocations WHERE run_id=?",
            (consult,),
        )
        .fetchall()
    )
    assert [dict(r) for r in rows] == [
        {"agent_role": "architect", "category": "consult"}
    ]
