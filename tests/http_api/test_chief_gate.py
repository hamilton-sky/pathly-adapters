"""chief-agent 08: the chief gate refuses every call a chief token's tier does not allow.

``chief_gate`` is a ``before_request`` hook registered right after ``_log_request``. It acts only
on a request that carries ``X-Pathly-Run-Token`` whose token row has role ``chief``; a builder
token, an unknown token and no token at all are untouched. For a chief it answers 401 when the
session is closed (a revoked chief token must never fall back to anonymous, because anonymous
loopback callers can do everything), 403 when the route is not listed or the tier lacks the
action, and 403 when the call names another project or posts as someone other than the chief.

The gate's own 403 always carries ``allowed``; a response without that key means the gate let the
call through to the route. That is how these tests tell "the gate refused" from "the route
answered".

The route table is data (``chief_routes.ROUTE_ACTIONS``), so one test walks the live
``app.url_map`` and checks that every non-GET route the table does not list is refused to the
strongest tier. A route added later is refused to the chief until someone lists it.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from pathlib import Path
from typing import NamedTuple

import pytest

# Rules the table lists before a later ticket adds the route (ticket 12 adds the directives
# route, and the table already maps it to ``decide``). A rule listed here may be missing from
# ``app.url_map``; any other listed rule that is missing fails the test.
PLANNED = {("/comms/directives", "POST")}

TIERS = ("status", "planner", "operator")


class Chief(NamedTuple):
    token: str
    run_id: str

    @property
    def headers(self) -> dict:
        return {"X-Pathly-Run-Token": self.token}


@pytest.fixture()
def app():
    from pathly_orchestrator.http_server import app as flask_app

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(autouse=True)
def _streams_do_not_block(app, monkeypatch):
    """Swap each ``/events/*`` view for a stub that answers at once.

    The real views stream until the client goes away and the test client waits for their first
    chunk, so a call the gate failed to refuse would hang the run instead of failing the test.
    The stub's answer has no ``allowed`` key, so a call that reaches it fails ``_gated``.
    """
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith("/events/"):
            monkeypatch.setitem(
                app.view_functions, rule.endpoint, lambda **_: ("stream ran", 200)
            )


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        yield c


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    root = tmp_path / "proj-a"
    root.mkdir()
    return root


@pytest.fixture()
def other_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj-b"
    root.mkdir()
    return root


def _chief(tier: str, root: Path) -> Chief:
    """A chief session of ``tier`` on ``root`` and its live token, made through the queries
    the way ``open_chief`` makes them (the spawn host is not needed to test the gate).
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries import chief as sessions
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    conn = get_db()
    run_id = "chief-" + secrets.token_hex(6)
    sessions.create_session(
        conn,
        run_id=run_id,
        project_root=str(root),
        preset=tier,
        tier=tier,
        engine="claude",
        tab_id=run_id,
        cli_session_id=None,
        hook_secret_hash=None,
        settings_dir=None,
    )
    token = mint_run_token(conn, run_id, "chief", None, str(root), "project", str(root))
    return Chief(token, run_id)


def _msg(type_, **extra) -> dict:
    body = {"feature": "demo", "from": "chief", "type": type_, "text": "hello"}
    body.update(extra)
    return body


def _gated(resp) -> bool:
    """True when this is the chief gate's own 403."""
    body = resp.get_json(silent=True) or {}
    return resp.status_code == 403 and "allowed" in body


def _passed(resp) -> bool:
    """True when the gate let the call through: the route (or Flask) answered it."""
    body = resp.get_json(silent=True) or {}
    return "allowed" not in body and resp.status_code != 401


def _count(sql: str, *params) -> int:
    from pathly_orchestrator.db.connection import get_db

    return get_db().execute(sql, params).fetchone()[0]


def _escalation(to_agent: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_messages import post_message

    return post_message(
        get_db(),
        board="feature",
        scope="demo",
        from_agent="builder",
        to_agent=to_agent,
        type="escalation",
        text="need a decision",
    )


# --- a status chief reads and cannot write ------------------------------------------------


def test_status_chief_reads_and_is_refused_a_note(client, project):
    chief = _chief("status", project)

    assert client.get("/comms?feature=demo", headers=chief.headers).status_code == 200

    resp = client.post("/comms/post", json=_msg("note"), headers=chief.headers)
    assert resp.status_code == 403
    body = resp.get_json()
    assert set(body) == {"error", "action", "tier", "allowed"}
    assert (body["action"], body["tier"], body["allowed"]) == (
        "post",
        "status",
        ["read"],
    )
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE type = 'note'") == 0


def test_the_route_still_gets_the_body_the_gate_read(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post", json=_msg("note", text="kept whole"), headers=chief.headers
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute(
            "SELECT text, from_agent, author_role, author_source FROM comms_messages"
            " WHERE id = ?",
            (resp.get_json()["message_id"],),
        )
        .fetchone()
    )
    assert tuple(row) == ("kept whole", "chief", "chief", "token")


# --- a planner posts a goal and cannot start a run ----------------------------------------


def test_planner_posts_a_goal_but_not_a_run(client, project):
    chief = _chief("planner", project)

    goal = client.post(
        "/comms/post", json=_msg("goal", text="Ship the export"), headers=chief.headers
    )
    assert goal.status_code == 200, goal.get_data(as_text=True)

    run = client.post("/runs", json={"kind": "flow"}, headers=chief.headers)
    assert run.status_code == 403
    body = run.get_json()
    assert (body["action"], body["tier"]) == ("run", "planner")
    assert body["allowed"] == ["plan", "post", "read"]


# --- the decompose routes: allowed for plan, overrides need run ---------------------------

DECOMPOSE = [
    ("/comms/goals/decompose", {"mode": "planner"}),
    ("/comms/features/decompose", {"rigor": "light"}),
    ("/comms/project/decompose", {"rigor": "bogus"}),
]
OVERRIDES = [
    {"prompt_override": "run exactly this"},
    {"stage_overrides": {"PLANNING": "run exactly this"}},
]


@pytest.mark.parametrize("path,base", DECOMPOSE, ids=[p for p, _ in DECOMPOSE])
@pytest.mark.parametrize("extra", OVERRIDES, ids=["prompt_override", "stage_overrides"])
def test_planner_overrides_need_run(client, project, path, base, extra):
    chief = _chief("planner", project)
    base = {**base, "project_root": str(project)}

    without = client.post(path, json=base, headers=chief.headers)
    assert _passed(without), without.get_data(as_text=True)

    with_overrides = client.post(path, json={**base, **extra}, headers=chief.headers)
    assert _gated(with_overrides)
    body = with_overrides.get_json()
    assert (body["action"], body["tier"]) == ("run", "planner")


def test_empty_overrides_do_not_need_run(client, project):
    chief = _chief("planner", project)

    resp = client.post(
        "/comms/goals/decompose",
        json={
            "mode": "planner",
            "prompt_override": "",
            "stage_overrides": {},
            "project_root": str(project),
        },
        headers=chief.headers,
    )

    assert _passed(resp), resp.get_data(as_text=True)


@pytest.mark.parametrize("extra", OVERRIDES, ids=["prompt_override", "stage_overrides"])
def test_overrides_on_a_read_route_need_run_too(client, project, extra):
    chief = _chief("planner", project)

    resp = client.post(
        "/comms/search",
        json={"query": "", "feature": "demo", **extra},
        headers=chief.headers,
    )

    assert _gated(resp)
    assert resp.get_json()["action"] == "run"


@pytest.mark.parametrize("path,base", DECOMPOSE, ids=[p for p, _ in DECOMPOSE])
def test_operator_passes_the_decompose_routes_with_overrides(
    client, project, path, base
):
    chief = _chief("operator", project)

    resp = client.post(
        path,
        json={
            **base,
            "project_root": str(project),
            "stage_overrides": {"PLANNING": "x"},
            "prompt_override": "y",
        },
        headers=chief.headers,
    )

    assert _passed(resp), resp.get_data(as_text=True)


def test_operator_passes_the_gate_on_a_run_start(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs",
        json={"kind": "bogus", "project_root": str(project)},
        headers=chief.headers,
    )

    assert resp.status_code == 400
    assert _passed(resp)


# --- unlisted routes are refused to every tier --------------------------------------------

UNLISTED = [
    ("post", "/db/query", {"sql": "SELECT 1"}),
    ("post", "/chief/open", {"engine": "claude"}),
    ("post", "/chief/close", {}),
    ("get", "/events/spawn", None),
    ("get", "/events/runner?topic=x", None),
    ("get", "/db/settings", None),
    ("put", "/db/settings/some.key", {"value": "1"}),
    ("post", "/skills/prompts", {"name": "x"}),
    ("post", "/comms/edit", {"message_id": "x", "text": "y"}),
    ("post", "/comms/delete", {"message_id": "x"}),
    ("post", "/comms/hydrate", {}),
    ("post", "/comms/tasks/status", {"task_ids": ["x"], "status": "done"}),
    ("post", "/complete_stage", {"force_past_gate": True}),
    ("post", "/runner/start", {}),
]


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize(
    "verb,path,body", UNLISTED, ids=[f"{u[0]} {u[1]}" for u in UNLISTED]
)
def test_unlisted_routes_are_refused_to_every_tier(
    client, project, tier, verb, path, body
):
    from pathly_orchestrator.supervisor.chief_tiers import actions_for

    chief = _chief(tier, project)

    kwargs = {"json": body} if body is not None else {}
    resp = getattr(client, verb)(path, headers=chief.headers, **kwargs)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    refusal = resp.get_json()
    assert refusal["tier"] == tier
    assert refusal["allowed"] == sorted(actions_for(tier))


# --- one project only ---------------------------------------------------------------------


def _calls(project_root: str):
    """Calls that name ``project_root``: in a body, in a query string, and on the chief route."""
    return [
        (
            "post",
            "/comms/search",
            {"json": {"query": "", "feature": "demo", "project_root": project_root}},
        ),
        (
            "get",
            "/comms",
            {"query_string": {"feature": "demo", "project_root": project_root}},
        ),
        ("get", "/chief/session", {"query_string": {"project_root": project_root}}),
    ]


@pytest.mark.parametrize("which", range(3))
def test_another_projects_root_is_refused(client, project, other_project, which):
    chief = _chief("operator", project)
    verb, path, kwargs = _calls(str(other_project))[which]

    resp = getattr(client, verb)(path, headers=chief.headers, **kwargs)

    assert _gated(resp)


@pytest.mark.parametrize("which", range(3))
@pytest.mark.parametrize("spelling", ["same", "trailing slash", "backslashes"])
def test_the_chiefs_own_project_passes_however_it_is_spelled(
    client, project, which, spelling
):
    chief = _chief("operator", project)
    root = str(project)
    root = {
        "same": root,
        "trailing slash": root + "/",
        "backslashes": root.replace("/", "\\"),
    }[spelling]
    verb, path, kwargs = _calls(root)[which]

    resp = getattr(client, verb)(path, headers=chief.headers, **kwargs)

    assert _passed(resp), resp.get_data(as_text=True)


@pytest.mark.parametrize("value", [["x"], 7, {"a": 1}, "  "])
def test_a_project_root_that_is_not_a_path_of_this_project_is_refused(
    client, project, value
):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/search",
        json={"query": "", "feature": "demo", "project_root": value},
        headers=chief.headers,
    )

    assert _gated(resp)


@pytest.mark.parametrize("value", [None, ""])
def test_an_unnamed_project_root_is_left_to_the_route(client, project, value):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/search",
        json={"query": "", "feature": "demo", "project_root": value},
        headers=chief.headers,
    )

    assert _passed(resp)


# --- a chief posts as the chief -----------------------------------------------------------


def test_a_post_from_another_role_is_refused(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post", json=_msg("note", **{"from": "builder"}), headers=chief.headers
    )

    assert _gated(resp)
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE type = 'note'") == 0


def test_a_post_without_from_is_refused(client, project):
    chief = _chief("operator", project)
    body = _msg("note")
    del body["from"]

    resp = client.post("/comms/post", json=body, headers=chief.headers)

    assert _gated(resp)


def test_a_chief_can_post_a_decision_on_the_project_board(client, project):
    chief = _chief("operator", project)
    root = str(project)

    resp = client.post(
        "/comms/post",
        json=_msg(
            "decision",
            text="no new dependencies",
            board="project",
            scope=root,
            project_root=root,
        ),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_a_saved_write_list_without_chief_keeps_the_existing_refusal(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_write_permissions

    root = str(project)
    set_write_permissions(get_db(), root, {"project": ["human"]})
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post",
        json=_msg("decision", board="project", scope=root, project_root=root),
        headers=chief.headers,
    )

    assert resp.status_code == 403
    body = resp.get_json()
    assert body["allowed_roles"] == ["human"]
    assert "allowed" not in body


def test_chief_is_a_default_project_writer():
    from pathly_orchestrator.db.queries.app_settings import (
        _DEFAULT_WRITE_PERMISSIONS,
    )
    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        _GLOBAL_WRITERS,
        _PROJECT_WRITERS,
    )

    assert "chief" in _PROJECT_WRITERS
    assert "chief" in _DEFAULT_WRITE_PERMISSIONS["project"]
    assert set(_DEFAULT_WRITE_PERMISSIONS["project"]) == set(_PROJECT_WRITERS)
    assert "chief" not in _GLOBAL_WRITERS
    assert "chief" not in _DEFAULT_WRITE_PERMISSIONS["global"]


# --- which action a post is ---------------------------------------------------------------


@pytest.mark.parametrize(
    "type_,action",
    [
        ("note", "post"),
        ("status", "post"),
        ("escalation", "post"),
        (5, "post"),
        ("goal", "plan"),
        ("task", "plan"),
        ("decision", "decide"),
        ("constraint", "decide"),
        ("Decision", "decide"),
        (" constraint ", "decide"),
    ],
)
def test_a_post_is_classed_by_its_type(client, project, type_, action):
    chief = _chief("status", project)

    resp = client.post("/comms/post", json=_msg(type_), headers=chief.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] == action


# --- listed routes: the action the table gives --------------------------------------------

LISTED = [
    ("/comms/goals/decompose", "plan"),
    ("/comms/features/decompose", "plan"),
    ("/comms/project/decompose", "plan"),
    ("/comms/supersede", "decide"),
    ("/runs", "run"),
    ("/comms/goals/run", "run"),
    ("/comms/run", "run"),
    ("/comms/tasks/run", "run"),
    ("/runs/x/stop", "stop"),
    ("/comms/goals/stop", "stop"),
    ("/comms/run/stop", "stop"),
    ("/comms/tasks/stop", "stop"),
    ("/runner/agent-answer", "answer"),
    ("/comms/answer", "answer"),
]


@pytest.mark.parametrize("path,action", LISTED, ids=[p for p, _ in LISTED])
def test_a_status_chief_is_refused_each_listed_route_by_its_action(
    client, project, path, action
):
    chief = _chief("status", project)

    resp = client.post(path, json={}, headers=chief.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] == action


@pytest.mark.parametrize(
    "path,body",
    [
        ("/comms/search", {"query": "", "feature": "demo"}),
        ("/code/query", {"project_root": "OWN"}),
    ],
)
def test_a_status_chief_may_call_the_read_routes(client, project, path, body):
    chief = _chief("status", project)
    body = {k: str(project) if v == "OWN" else v for k, v in body.items()}

    resp = client.post(path, json=body, headers=chief.headers)

    assert _passed(resp)


def test_a_chief_may_read_its_own_session(client, project):
    chief = _chief("status", project)

    resp = client.get(
        "/chief/session",
        query_string={"project_root": str(project)},
        headers=chief.headers,
    )

    assert resp.status_code == 200
    assert resp.get_json()["open"] is True


# --- run control verbs --------------------------------------------------------------------

VERBS = [
    ("pause", "run"),
    ("resume", "run"),
    ("advance", "run"),
    ("reroute", "run"),
    ("retry", "run"),
    ("abort", "stop"),
    ("stop", "stop"),
]


@pytest.mark.parametrize("verb,action", VERBS)
def test_run_control_verbs_are_run_or_stop(client, project, verb, action):
    from pathly_orchestrator.supervisor.chief_tiers import actions_for

    planner = _chief("planner", project)
    resp = client.post(f"/runs/x/{verb}", json={}, headers=planner.headers)
    assert _gated(resp)
    assert resp.get_json()["action"] == action

    assert action in actions_for("operator")
    operator = _chief("operator", project)
    # `retry` starts a run in the directory its own body names, so it names the project.
    body = {"project_root": str(project)} if verb == "retry" else {}
    resp = client.post(f"/runs/x/{verb}", json=body, headers=operator.headers)
    assert _passed(resp), resp.get_data(as_text=True)


def test_an_unknown_run_verb_is_unlisted(client, project):
    operator = _chief("operator", project)

    resp = client.post("/runs/x/bogus", json={}, headers=operator.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] is None


# --- acknowledging a human escalation is an answer ----------------------------------------


@pytest.mark.parametrize("to_agent", ["human", "Human", " human "])
def test_acknowledging_a_human_escalation_is_an_answer(client, project, to_agent):
    chief = _chief("status", project)
    message_id = _escalation(to_agent)

    resp = client.post(
        "/comms/acknowledge",
        json={"message_id": message_id, "agent": "chief"},
        headers=chief.headers,
    )

    assert _gated(resp)
    assert resp.get_json()["action"] == "answer"


def test_acknowledging_any_other_row_is_a_decision(client, project):
    chief = _chief("status", project)
    ordinary = _escalation("builder")

    for message_id in (ordinary, "no-such-row"):
        resp = client.post(
            "/comms/acknowledge",
            json={"message_id": message_id, "agent": "chief"},
            headers=chief.headers,
        )
        assert _gated(resp)
        assert resp.get_json()["action"] == "decide"


def test_an_operator_acknowledges_an_ordinary_row_and_meets_the_human_gate(
    client, project
):
    chief = _chief("operator", project)

    ok = client.post(
        "/comms/acknowledge",
        json={"message_id": _escalation("builder"), "agent": "chief"},
        headers=chief.headers,
    )
    assert ok.status_code == 200

    # The operator holds `answer`, so the gate lets it through; the existing human gate
    # (ticket 10 gives the chief a way past it) still answers for any live run token.
    human = client.post(
        "/comms/acknowledge",
        json={"message_id": _escalation("human"), "agent": "chief"},
        headers=chief.headers,
    )
    assert _passed(human)
    assert human.status_code == 403
    assert "human" in human.get_json()["error"]


# --- a closed session is a 401, never anonymous --------------------------------------------


def test_a_revoked_chief_token_gets_401(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import revoke_run_tokens

    chief = _chief("operator", project)
    assert client.get("/comms?feature=demo", headers=chief.headers).status_code == 200
    revoke_run_tokens(get_db(), chief.run_id)

    calls = [
        client.get("/comms?feature=demo", headers=chief.headers),
        client.post("/db/query", json={"sql": "SELECT 1"}, headers=chief.headers),
        client.get("/no/such/route", headers=chief.headers),
    ]
    for resp in calls:
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "chief session closed"}


def test_a_live_chief_token_of_a_closed_session_gets_401(client, project):
    from pathly_orchestrator.db.connection import get_db

    chief = _chief("operator", project)
    conn = get_db()
    conn.execute(
        "UPDATE chief_sessions SET closed_at = 1.0 WHERE run_id = ?", (chief.run_id,)
    )
    conn.commit()

    resp = client.get("/comms?feature=demo", headers=chief.headers)

    assert resp.status_code == 401
    assert resp.get_json() == {"error": "chief session closed"}


def test_a_chief_token_without_a_session_gets_401(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    token = mint_run_token(
        get_db(),
        "chief-000000000000",
        "chief",
        None,
        str(project),
        "project",
        str(project),
    )

    resp = client.get("/comms?feature=demo", headers={"X-Pathly-Run-Token": token})

    assert resp.status_code == 401


def test_closing_the_session_through_the_queries_ends_the_chief(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries import chief as sessions

    chief = _chief("operator", project)
    assert sessions.close_session(get_db(), chief.run_id, "tab closed")

    resp = client.post("/comms/post", json=_msg("note"), headers=chief.headers)

    assert resp.status_code == 401


# --- paths no route matches ---------------------------------------------------------------


def test_an_unknown_path_is_a_404_and_a_wrong_method_a_405(client, project):
    chief = _chief("status", project)

    assert client.get("/no/such/route", headers=chief.headers).status_code == 404
    assert (
        client.post("/no/such/route", json={}, headers=chief.headers).status_code == 404
    )
    assert client.get("/comms/post", headers=chief.headers).status_code == 405
    assert client.delete("/comms", headers=chief.headers).status_code == 405


# --- other callers are untouched ----------------------------------------------------------


def test_builder_unknown_and_missing_tokens_are_unaffected(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    builder = mint_run_token(
        get_db(), "run-b", "builder", "demo", str(project), "feature", "demo"
    )
    callers = [{}, {"X-Pathly-Run-Token": builder}, {"X-Pathly-Run-Token": "nope"}]

    for headers in callers:
        query = client.post("/db/query", json={"sql": "SELECT 1 AS n"}, headers=headers)
        assert query.status_code == 200, headers
        settings = client.get("/db/settings", headers=headers)
        assert settings.status_code == 200, headers
        post = client.post(
            "/comms/post", json=_msg("note", **{"from": "builder"}), headers=headers
        )
        assert post.status_code == 200, headers


def test_a_revoked_builder_token_is_still_anonymous_not_401(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import (
        mint_run_token,
        revoke_run_tokens,
    )

    conn = get_db()
    token = mint_run_token(
        conn, "run-r", "builder", "demo", str(project), "feature", "demo"
    )
    revoke_run_tokens(conn, "run-r")

    resp = client.post(
        "/db/query", json={"sql": "SELECT 1"}, headers={"X-Pathly-Run-Token": token}
    )

    assert resp.status_code == 200


# --- the table ----------------------------------------------------------------------------


def _routed(app) -> set[tuple[str, str]]:
    return {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods
    }


def test_every_listed_rule_exists(app):
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS

    missing = set(ROUTE_ACTIONS) - _routed(app) - PLANNED

    assert not missing, f"the table lists rules no route has: {sorted(missing)}"
    assert PLANNED <= set(ROUTE_ACTIONS), "PLANNED names a rule the table does not list"


def test_every_listed_action_is_a_tier_action():
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS
    from pathly_orchestrator.supervisor.chief_tiers import ACTIONS

    assert set(ROUTE_ACTIONS.values()) <= set(ACTIONS)


def test_reads_are_every_get_except_the_secret_bearing_ones():
    from pathly_orchestrator.http_server.chief_routes import action_for

    def classify(rule, method="GET"):
        return action_for(rule, method, {}, {}, lambda message_id: False)

    assert classify("/comms") == "read"
    assert classify("/runs/<run_id>") == "read"
    assert classify("/hq/context") == "read"
    assert classify("/chief/session") == "read"
    assert classify("/events/spawn") is None
    assert classify("/events/runner") is None
    assert classify("/events/comms") is None
    assert classify("/db/settings") is None
    assert classify("/db/settings/<key>", "PUT") is None


def test_every_unlisted_non_get_route_is_refused_to_an_operator(
    app, client, project, monkeypatch
):
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS

    exits: list[int] = []
    # /shutdown ends the process on a timer; a refused call never reaches it.
    monkeypatch.setattr(os, "_exit", lambda code=0: exits.append(code))
    operator = _chief("operator", project)
    adapter = app.url_map.bind("localhost")

    non_get = {
        (rule.rule, method): rule
        for rule in app.url_map.iter_rules()
        for method in rule.methods - {"GET", "HEAD", "OPTIONS"}
    }
    unlisted = {key: rule for key, rule in non_get.items() if key not in ROUTE_ACTIONS}
    assert {
        ("/db/query", "POST"),
        ("/chief/open", "POST"),
        ("/shutdown", "POST"),
        ("/comms/delete", "POST"),
        ("/db/settings/<key>", "PUT"),
    } <= set(unlisted)
    assert set(non_get) - set(unlisted) == set(ROUTE_ACTIONS) & set(non_get)

    not_gated = []
    for (rule_text, method), rule in sorted(unlisted.items()):
        built = rule.build({name: "x" for name in rule.arguments}, append_unknown=False)
        assert built is not None, rule_text
        path = built[1]
        matched, _ = adapter.match(path, method=method, return_rule=True)
        assert (
            matched.rule == rule_text
        ), f"{path} matched {matched.rule}, not {rule_text}"
        resp = client.open(
            path,
            method=method,
            headers=operator.headers,
            data=b"{}",
            content_type="application/json",
        )
        if not _gated(resp):
            not_gated.append((method, rule_text, resp.status_code))

    assert exits == []
    assert not_gated == []


# --- the gate reads the body the way the route will ---------------------------------------
#
# The comms routes read the body with ``read_json_body`` (UTF-8, then cp1252, whatever the
# content type); ``/runs``, ``/runner/agent-answer``, ``/code/query`` and ``/runs/<id>/<verb>``
# read it with ``get_json``, which hands the raw bytes to ``json.loads`` (a BOM, UTF-16 and
# UTF-32 are all understood). A body only the second reader understands used to look like ``{}``
# to the gate, so the project binding never ran.

ENCODINGS = [
    "utf-8-sig",
    "utf-16",
    "utf-16-le",
    "utf-16-be",
    "utf-32",
    "utf-32-le",
    "utf-32-be",
]
WITH_PLAIN = [None, *ENCODINGS]


def _send(client, path, payload, encoding, headers):
    """POST ``payload`` as plain JSON, or as JSON text in ``encoding`` (BOM, UTF-16, UTF-32)."""
    if encoding is None:
        return client.post(path, json=payload, headers=headers)
    return client.post(
        path,
        data=json.dumps(payload).encode(encoding),
        content_type="application/json",
        headers=headers,
    )


@pytest.fixture()
def started(monkeypatch):
    """Record the board runs the routes start, instead of starting any."""
    calls: list[dict] = []

    def fake(*args, **kwargs):
        calls.append(kwargs)
        return {"ok": True, "run_id": "r-1"}

    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.board_run.start_board_run", fake
    )
    return calls


@pytest.fixture(autouse=True)
def _no_reindex(monkeypatch):
    """``/code/query`` fires a background re-index of the project it names; keep it off."""
    monkeypatch.setattr(
        "pathly_orchestrator.runner.code_context.maybe_reindex", lambda root: None
    )


@pytest.fixture(autouse=True)
def _no_code_backend(monkeypatch):
    """Resolve the code-intelligence backend to ``none``: no Serena session starts in a test."""
    monkeypatch.setattr(
        "pathly_orchestrator.runner.code_context._resolve_backend", lambda: "none"
    )


def _run_spec(root: Path) -> dict:
    return {
        "kind": "single",
        "board": "feature",
        "scope": "demo",
        "project_root": str(root),
    }


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_runs_refuses_another_project_however_the_body_is_encoded(
    client, project, other_project, started, encoding
):
    chief = _chief("operator", project)

    resp = _send(client, "/runs", _run_spec(other_project), encoding, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert started == []


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_runs_hands_the_route_the_whole_body_of_its_own_project(
    client, project, started, encoding
):
    chief = _chief("operator", project)

    resp = _send(client, "/runs", _run_spec(project), encoding, chief.headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert [c["project_root"] for c in started] == [str(project)]


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_agent_answer_refuses_another_project_however_the_body_is_encoded(
    client, project, other_project, encoding
):
    chief = _chief("operator", project)
    body = {"topic": "t", "answer": "a", "project_root": str(other_project)}

    resp = _send(client, "/runner/agent-answer", body, encoding, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_agent_answer_of_its_own_project_reaches_the_route(client, project, encoding):
    chief = _chief("operator", project)
    body = {"topic": "t", "answer": "a", "project_root": str(project)}

    resp = _send(client, "/runner/agent-answer", body, encoding, chief.headers)

    # The route read the topic and the answer from the body: no run has that topic.
    assert resp.status_code == 404, resp.get_data(as_text=True)
    assert _passed(resp)


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_code_query_refuses_another_project_however_the_body_is_encoded(
    client, project, other_project, encoding
):
    chief = _chief("status", project)
    body = {
        "op": "impact",
        "target": "a.py",
        "scope": "(interactive)",
        "project_root": str(other_project),
    }

    resp = _send(client, "/code/query", body, encoding, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_code_query_of_its_own_project_reaches_the_route(client, project, encoding):
    chief = _chief("status", project)
    body = {
        "op": "impact",
        "target": "a.py",
        "scope": "(interactive)",
        "project_root": str(project),
    }

    resp = _send(client, "/code/query", body, encoding, chief.headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _passed(resp)


@pytest.mark.parametrize("verb", ["retry", "reroute"])
@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_run_control_refuses_another_project_however_the_body_is_encoded(
    client, project, other_project, verb, encoding
):
    chief = _chief("operator", project)
    body = {"project_root": str(other_project)}

    resp = _send(client, f"/runs/x/{verb}", body, encoding, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])


@pytest.mark.parametrize("encoding", ENCODINGS)
def test_an_encoded_body_is_classed_by_its_type_too(client, project, encoding):
    chief = _chief("status", project)

    resp = _send(client, "/comms/post", _msg("decision"), encoding, chief.headers)

    assert _gated(resp)
    assert resp.get_json()["action"] == "decide"


def test_the_gate_does_not_change_what_a_route_reads(client, project, started):
    """A body the route ignores (no JSON content type) stays ignored: the gate adds no cache."""
    chief = _chief("operator", project)

    resp = client.post(
        "/runs",
        data=json.dumps(_run_spec(project)),
        content_type="text/plain",
        headers=chief.headers,
    )

    assert resp.status_code == 400
    assert "kind" in resp.get_json()["error"]
    assert started == []


# --- a body that is not UTF-8 (cp1252, as a Windows shell sends it) ------------------------


def _cp1252(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("cp1252")


def test_a_cp1252_body_is_classed_by_its_type(client, project):
    chief = _chief("status", project)
    body = _cp1252(_msg("decision", text="keep it \u2014 simple"))
    assert b"\x97" in body

    resp = client.post(
        "/comms/post", data=body, content_type="application/json", headers=chief.headers
    )

    assert _gated(resp)
    assert resp.get_json()["action"] == "decide"


@pytest.mark.parametrize("path", ["/comms/search", "/runs", "/code/query"])
def test_a_cp1252_body_naming_another_project_is_refused(
    client, project, other_project, path
):
    chief = _chief("operator", project)
    body = _cp1252(
        {
            "query": "caf\u00e9 \u2014",
            "feature": "demo",
            "project_root": str(other_project),
        }
    )

    resp = client.post(
        path, data=body, content_type="application/json", headers=chief.headers
    )

    assert _gated(resp)
    assert "project" in resp.get_json()["error"]


def test_an_operator_cp1252_post_is_stored_whole(client, project):
    chief = _chief("operator", project)
    body = _cp1252(_msg("note", text="kept \u2014 whole"))

    resp = client.post(
        "/comms/post", data=body, content_type="application/json", headers=chief.headers
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert (
        _count(
            "SELECT COUNT(*) FROM comms_messages WHERE text = ?", "kept \u2014 whole"
        )
        == 1
    )


# --- HEAD, redirects and paths no route matches -------------------------------------------


def test_head_is_read_as_get(client, project):
    chief = _chief("status", project)

    assert client.head("/comms?feature=demo", headers=chief.headers).status_code == 200
    for path in ("/events/spawn", "/events/runner?topic=x", "/db/settings"):
        assert client.head(path, headers=chief.headers).status_code == 403, path


def test_a_post_only_route_has_no_head(client, project):
    chief = _chief("operator", project)

    assert client.head("/db/query", headers=chief.headers).status_code == 405


REDIRECTED = [
    ("post", "/db//query", {"sql": "SELECT 1 AS n"}),
    ("post", "/comms//post", _msg("note")),
    ("get", "/events//spawn", None),
    ("get", "/db//settings", None),
]


@pytest.mark.parametrize(
    "verb,path,body", REDIRECTED, ids=[f"{v} {p}" for v, p, _ in REDIRECTED]
)
def test_a_redirect_runs_no_view_and_its_target_is_gated(
    client, project, verb, path, body
):
    chief = _chief("operator", project)
    kwargs = {"json": body} if body is not None else {}

    first = getattr(client, verb)(path, headers=chief.headers, **kwargs)
    assert first.status_code == 308, (first.status_code, first.get_data(as_text=True))

    followed = getattr(client, verb)(
        path, headers=chief.headers, follow_redirects=True, **kwargs
    )
    if path.startswith("/comms"):
        assert followed.status_code == 200
    else:
        assert _gated(followed), (followed.status_code, followed.get_data(as_text=True))
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE type = 'note'") == (
        1 if path.startswith("/comms") else 0
    )


NOT_RUN_PATHS = [
    "/DB/query",
    "/db/query/",
    "/db/./query",
    "//db/query",
    "/comms/../db/query",
    "/db/query;x=1",
    "/db/query%00",
    "/db/query%2F",
]


@pytest.mark.parametrize("path", NOT_RUN_PATHS)
def test_a_lookalike_path_never_reaches_an_unlisted_view(client, project, path):
    chief = _chief("operator", project)

    resp = client.post(path, json={"sql": "SELECT 1 AS n"}, headers=chief.headers)

    assert _gated(resp) or resp.status_code in (308, 404, 405), (
        resp.status_code,
        resp.get_data(as_text=True)[:200],
    )


@pytest.mark.parametrize("method", ["put", "delete", "patch"])
@pytest.mark.parametrize("path", ["/db/query", "/events/spawn", "/comms/delete"])
def test_a_method_no_route_has_is_a_405(client, project, method, path):
    chief = _chief("operator", project)

    resp = getattr(client, method)(path, headers=chief.headers)

    assert resp.status_code == 405


# --- the project board is named by `scope` too --------------------------------------------


def _board_count(root: Path | str) -> int:
    return _count(
        "SELECT COUNT(*) FROM comms_messages WHERE board = 'project' AND scope = ?",
        str(root),
    )


@pytest.mark.parametrize(
    "fields",
    [
        {"scope": "OTHER"},
        {"scope": "OTHER", "project_root": "OWN"},
        {"scope": "OTHER/"},
        {"feature": "OTHER"},
        {"feature": "OTHER", "scope": "  "},
        {"feature": "OTHER", "scope": ["x"]},
        {"feature": "OTHER", "scope": None},
        {"scope": "demo"},
        {},
    ],
    ids=lambda f: ",".join(f) or "nothing",
)
def test_a_project_board_post_must_name_the_chiefs_project_in_scope(
    client, project, other_project, fields
):
    chief = _chief("operator", project)
    fields = {
        k: (
            str(other_project) + ("/" if v == "OTHER/" else "")
            if isinstance(v, str) and v.startswith("OTHER")
            else str(project) if v == "OWN" else v
        )
        for k, v in fields.items()
    }

    resp = client.post(
        "/comms/post",
        json=_msg("decision", board="project", **fields),
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert _board_count(other_project) == 0
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE type = 'decision'") == 0


@pytest.mark.parametrize("spelling", ["same", "trailing slash", "backslashes"])
def test_a_project_board_post_to_its_own_scope_passes(client, project, spelling):
    chief = _chief("operator", project)
    root = str(project)
    scope = {
        "same": root,
        "trailing slash": root + "/",
        "backslashes": root.replace("/", "\\"),
    }[spelling]

    resp = client.post(
        "/comms/post",
        json=_msg("decision", board="project", scope=scope),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_a_feature_board_post_is_not_bound_by_its_scope(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post",
        json=_msg("note", board="feature", scope="some-feature"),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)


@pytest.mark.parametrize("encoding", ENCODINGS)
def test_a_project_board_post_is_bound_in_any_encoding(
    client, project, other_project, encoding
):
    chief = _chief("operator", project)
    body = _msg("decision", board="project", scope=str(other_project))

    resp = _send(client, "/comms/post", body, encoding, chief.headers)

    assert _gated(resp)
    assert "project" in resp.get_json()["error"]
    assert _board_count(other_project) == 0


@pytest.mark.parametrize(
    "path", ["/runs", "/comms/run", "/comms/run/stop"], ids=lambda p: p
)
def test_a_run_on_another_projects_board_is_refused(
    client, project, other_project, started, path
):
    chief = _chief("operator", project)
    body = {
        "kind": "single",
        "board": "project",
        "scope": str(other_project),
        "project_root": str(project),
    }

    resp = client.post(path, json=body, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert started == []


def test_a_run_on_its_own_projects_board_passes(client, project, started):
    chief = _chief("operator", project)
    body = {
        "kind": "single",
        "board": "project",
        "scope": str(project),
        "project_root": str(project),
    }

    resp = client.post("/runs", json=body, headers=chief.headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert len(started) == 1


def test_the_project_decompose_override_must_be_the_chiefs_project(
    client, project, other_project
):
    chief = _chief("planner", project)
    base = {"rigor": "bogus", "project_root": str(project)}

    other = client.post(
        "/comms/project/decompose",
        json={**base, "project": str(other_project)},
        headers=chief.headers,
    )
    assert _gated(other)

    for project_field in ("project", "  ", str(project), str(project) + "/"):
        ok = client.post(
            "/comms/project/decompose",
            json={**base, "project": project_field},
            headers=chief.headers,
        )
        assert _passed(ok), (project_field, ok.get_data(as_text=True))


def _code_query(client, chief, project, **fields):
    body = {
        "op": "impact",
        "target": "a.py",
        "role": "architect",
        "project_root": str(project),
        **fields,
    }
    return client.post("/code/query", json=body, headers=chief.headers)


@pytest.mark.parametrize(
    "fields",
    [{"scope": "OTHER"}, {"feature": "OTHER"}, {"scope": "some-feature"}],
    ids=["scope", "feature", "a feature name"],
)
def test_a_code_query_logs_to_the_project_board_so_its_scope_must_be_this_projects(
    client, project, other_project, fields
):
    chief = _chief("status", project)
    fields = {k: str(other_project) if v == "OTHER" else v for k, v in fields.items()}

    resp = _code_query(client, chief, project, **fields)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert _board_count(other_project) == 0
    assert (
        _count("SELECT COUNT(*) FROM comms_messages WHERE from_agent = 'code-intel'")
        == 0
    )


@pytest.mark.parametrize(
    "fields,logged",
    [
        ({}, 0),
        ({"scope": "(interactive)"}, 0),
        ({"scope": "   "}, 0),
        ({"scope": "OWN"}, 1),
        ({"scope": "OWN/"}, 1),
        ({"feature": "OWN"}, 1),
    ],
    ids=["no scope", "a marker", "blank", "own root", "own root, slash", "own feature"],
)
def test_a_code_query_of_this_project_or_with_a_marker_scope_passes(
    client, project, fields, logged
):
    chief = _chief("status", project)
    fields = {k: v.replace("OWN", str(project)) for k, v in fields.items()}

    resp = _code_query(client, chief, project, **fields)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _passed(resp)
    assert (
        _count("SELECT COUNT(*) FROM comms_messages WHERE from_agent = 'code-intel'")
        == logged
    )


# --- a run or decompose route needs the project named -------------------------------------
#
# Left out, the routes fall back to the server's working directory, which can be another
# project. The chief names its own project on every route that starts an agent.

NAMES_A_PROJECT = [
    ("/runs", {"kind": "bogus"}),
    ("/comms/goals/run", {"goal_id": "x"}),
    ("/comms/run", {"scope": "demo"}),
    ("/comms/tasks/run", {"message_id": "x"}),
    ("/comms/goals/decompose", {"mode": "planner"}),
    ("/comms/features/decompose", {"rigor": "light"}),
    ("/comms/project/decompose", {"rigor": "bogus"}),
]


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT, ids=[p for p, _ in NAMES_A_PROJECT]
)
@pytest.mark.parametrize("value", ["absent", None, "", 0, []])
def test_a_chief_that_names_no_project_is_refused_on_a_run_route(
    client, project, path, body, value
):
    chief = _chief("operator", project)
    sent = dict(body) if value == "absent" else {**body, "project_root": value}

    resp = client.post(path, json=sent, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT, ids=[p for p, _ in NAMES_A_PROJECT]
)
def test_a_chief_that_names_its_project_passes_a_run_route(client, project, path, body):
    chief = _chief("operator", project)

    resp = client.post(
        path, json={**body, "project_root": str(project)}, headers=chief.headers
    )

    assert _passed(resp), resp.get_data(as_text=True)


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT[4:], ids=[p for p, _ in NAMES_A_PROJECT[4:]]
)
def test_a_planner_that_names_no_project_is_refused_on_a_decompose_route(
    client, project, path, body
):
    chief = _chief("planner", project)

    resp = client.post(path, json=body, headers=chief.headers)

    assert _gated(resp)
    assert "project_root" in resp.get_json()["error"]


def test_a_project_named_only_in_the_query_string_does_not_count(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs?project_root=" + str(project),
        json={"kind": "bogus"},
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


# --- round 3: what every route reads as a project, board, scope or file -------------------
#
# Two rounds each left one hole of the same class: a request field a route reads as a project,
# a board or a scope that the gate did not look at (a query-string `project_root` on a route that
# reads the body, `/comms/search`'s `feature` fallback, `GET /comms?board=project&scope=...`, an
# absolute `/code/query` target). `chief_fields.ROUTE_FIELDS` now says, per route the chief can
# reach, which fields it reads that way, and `chief_project` applies that one table to the body
# and the query string.


@pytest.mark.parametrize(
    "path,body", NAMES_A_PROJECT, ids=[p for p, _ in NAMES_A_PROJECT]
)
def test_a_project_named_only_in_the_query_string_does_not_name_it(
    client, project, path, body
):
    chief = _chief("operator", project)

    resp = client.post(
        path,
        query_string={"project_root": str(project)},
        json=body,
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


def test_the_route_reads_the_body_so_the_body_must_carry_the_root(
    client, project, started
):
    chief = _chief("operator", project)
    spec = {"kind": "single", "board": "feature", "scope": "demo"}

    query_only = client.post(
        "/runs",
        query_string={"project_root": str(project)},
        json=spec,
        headers=chief.headers,
    )
    in_body = client.post(
        "/runs", json={**spec, "project_root": str(project)}, headers=chief.headers
    )

    assert _gated(query_only)
    assert in_body.status_code == 200, in_body.get_data(as_text=True)
    assert [c["project_root"] for c in started] == [str(project)]


def _seed_board(root: Path | str, text: str) -> None:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_messages import post_message

    post_message(
        get_db(),
        board="project",
        scope=str(root),
        from_agent="chief",
        type="decision",
        text=text,
    )


# `/comms/search` reads `data.get("scope") or feature`.
@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("scope", ["absent", 0, None, "", False, []], ids=repr)
def test_a_search_of_the_project_board_falls_back_to_feature_and_that_is_bound(
    client, project, other_project, tier, scope
):
    _seed_board(other_project, "zebra decision of the other project")
    chief = _chief(tier, project)
    body = {
        "query": "zebra",
        "board": "project",
        "feature": str(other_project),
        "mode": "keyword",
    }
    if scope != "absent":
        body["scope"] = scope

    resp = client.post("/comms/search", json=body, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "zebra" not in resp.get_data(as_text=True)


@pytest.mark.parametrize("tier", TIERS)
def test_a_search_of_its_own_project_board_passes_by_scope_or_by_feature(
    client, project, other_project, tier
):
    _seed_board(project, "zebra decision of this project")
    _seed_board(other_project, "zebra decision of the other project")
    chief = _chief(tier, project)

    for fields in ({"scope": str(project)}, {"feature": str(project)}):
        resp = client.post(
            "/comms/search",
            json={
                "query": "zebra",
                "board": "project",
                "mode": "keyword",
                **{"feature": "demo", **fields},
            },
            headers=chief.headers,
        )
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert "other project" not in resp.get_data(as_text=True)


def test_a_search_of_a_feature_board_is_not_bound(client, project):
    chief = _chief("status", project)

    resp = client.post(
        "/comms/search",
        json={"query": "zebra", "feature": "demo", "mode": "keyword"},
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)


BOARD_LISTS = ["/comms", "/comms/tasks", "/comms/goals"]


# The GET board reads read `board`, then `scope or feature`, with `.strip()` on the board.
@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("path", BOARD_LISTS)
@pytest.mark.parametrize(
    "how", ["scope", "feature", "padded board", "scope and feature"]
)
def test_a_board_read_of_another_projects_board_is_refused(
    client, project, other_project, tier, path, how
):
    _seed_board(other_project, "zebra decision of the other project")
    chief = _chief(tier, project)
    other = str(other_project)
    query = {
        "scope": {"feature": "x", "board": "project", "scope": other},
        "feature": {"feature": other, "board": "project"},
        "padded board": {"feature": "x", "board": " project ", "scope": other},
        "scope and feature": {"feature": other, "board": "project", "scope": other},
    }[how]

    resp = client.get(path, query_string=query, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "zebra" not in resp.get_data(as_text=True)


@pytest.mark.parametrize("path", BOARD_LISTS)
def test_a_board_read_of_its_own_board_or_of_a_feature_board_passes(
    client, project, other_project, path
):
    _seed_board(project, "zebra decision of this project")
    _seed_board(other_project, "zebra decision of the other project")
    chief = _chief("status", project)
    own = str(project)

    for query in (
        {"feature": "x", "board": "project", "scope": own},
        {"feature": own, "board": "project"},
        {"feature": "x", "board": "project", "scope": own + "/"},
        {"feature": "demo"},
        {"feature": "demo", "board": "feature", "scope": "some-feature"},
        {"feature": "demo", "board": "global"},
    ):
        resp = client.get(path, query_string=query, headers=chief.headers)
        assert resp.status_code == 200, (query, resp.get_data(as_text=True)[:200])
        assert "other project" not in resp.get_data(as_text=True)


def test_a_board_read_of_its_own_board_returns_the_board(client, project):
    _seed_board(project, "zebra decision of this project")
    chief = _chief("status", project)

    resp = client.get(
        "/comms",
        query_string={"feature": "x", "board": "project", "scope": str(project)},
        headers=chief.headers,
    )

    assert "zebra decision of this project" in resp.get_data(as_text=True)


# Reads that take a board and a scope, or only a scope, or a board id.
OTHER_BOARD_READS = [
    ("/comms/artifacts", {"board": "project", "scope": "OTHER"}),
    ("/comms/run/status", {"board": "project", "scope": "OTHER"}),
    ("/comms/trash", {"scope": "OTHER"}),
    ("/comms/artifacts/section", {"scope": "OTHER", "project_root": "OWN"}),
    ("/comms/artifacts/section", {"feature": "OTHER", "project_root": "OWN"}),
    ("/comms/artifacts/x/section", {"scope": "OTHER"}),
    ("/hq/context", {"board": "OTHER"}),
]


@pytest.mark.parametrize(
    "path,query",
    OTHER_BOARD_READS,
    ids=[f"{p} {sorted(q)}" for p, q in OTHER_BOARD_READS],
)
def test_the_other_reads_of_a_board_are_bound_too(
    client, project, other_project, path, query
):
    chief = _chief("status", project)
    query = {
        k: str(other_project) if v == "OTHER" else str(project) if v == "OWN" else v
        for k, v in query.items()
    }

    resp = client.get(path, query_string=query, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])


@pytest.mark.parametrize(
    "path,query",
    [
        ("/comms/artifacts", {"board": "project", "scope": "OWN"}),
        ("/comms/artifacts", {"board": "feature", "scope": "some-feature"}),
        ("/comms/run/status", {"board": "project", "scope": "OWN"}),
        ("/comms/trash", {"scope": "OWN"}),
        ("/comms/trash", {"scope": "some-feature"}),
        ("/comms/artifacts/section", {"scope": "some-feature", "project_root": "OWN"}),
        ("/hq/context", {"board": "OWN"}),
        ("/hq/context", {"board": "some-feature"}),
    ],
)
def test_the_other_reads_of_its_own_board_pass(client, project, path, query):
    chief = _chief("status", project)
    query = {k: str(project) if v == "OWN" else v for k, v in query.items()}

    resp = client.get(path, query_string=query, headers=chief.headers)

    assert _passed(resp), (resp.status_code, resp.get_data(as_text=True)[:200])


# Reads whose project filter is optional and falls back to the server's own project, or to every
# project: the chief names its project on each.
NAMES_A_PROJECT_READS = [
    "/db/features",
    "/db/stats",
    "/db/stats/trends",
    "/db/recent",
    "/db/rollup",
    "/db/features/<feature>/agents",
    "/db/features/<feature>/events",
    "/db/features/<feature>/otel",
    "/db/features/<feature>/runs",
    "/status",
    "/comms/artifacts/section",
]


@pytest.mark.parametrize("rule", NAMES_A_PROJECT_READS)
def test_a_read_that_falls_back_to_another_project_must_name_the_chiefs(
    client, project, other_project, rule
):
    path = rule.replace("<feature>", "x")
    chief = _chief("status", project)

    unnamed = client.get(path, headers=chief.headers)
    other = client.get(
        path, query_string={"project_root": str(other_project)}, headers=chief.headers
    )
    own = client.get(
        path, query_string={"project_root": str(project)}, headers=chief.headers
    )

    assert _gated(unnamed), (unnamed.status_code, unnamed.get_data(as_text=True)[:200])
    assert "project_root" in unnamed.get_json()["error"]
    assert _gated(other)
    assert _passed(own), (own.status_code, own.get_data(as_text=True)[:200])


def test_a_read_that_filters_by_project_is_bound_by_its_query_string(
    client, project, other_project
):
    chief = _chief("status", project)

    for path in ("/runs", "/api/features", "/skills/prompts", "/comms/permissions"):
        other = client.get(
            path,
            query_string={"project_root": str(other_project)},
            headers=chief.headers,
        )
        own = client.get(
            path, query_string={"project_root": str(project)}, headers=chief.headers
        )
        assert _gated(other), path
        assert _passed(own), (path, own.get_data(as_text=True)[:200])


# --- /code/query: the target is a file ----------------------------------------------------


def _target(client, chief, project, target, **fields):
    return _code_query(
        client, chief, project, target=target, scope="(interactive)", **fields
    )


@pytest.mark.parametrize(
    "target",
    [
        "OTHER/src/x.py",
        "OTHER\\src\\x.py",
        "OTHER/../proj-b/x.py",
        "OWN/../proj-b/x.py",
        "../proj-b/x.py",
        "src/../../proj-b/x.py",
        "C:\\Users\\someone\\other\\x.py",
        "C:/Users/someone/other/x.py",
        "c:x.py",
        "/etc/passwd",
        "//server/share/x.py",
    ],
)
@pytest.mark.parametrize("tier", TIERS)
def test_a_code_query_target_outside_the_project_is_refused(
    client, project, other_project, target, tier
):
    chief = _chief(tier, project)
    target = target.replace("OTHER", str(other_project)).replace("OWN", str(project))

    resp = _target(client, chief, project, target)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project" in resp.get_json()["error"]


def test_a_code_query_target_outside_the_project_is_refused_with_another_root(
    client, project, other_project
):
    chief = _chief("status", project)
    body = {
        "op": "impact",
        "target": str(other_project / "x.py"),
        "scope": "(interactive)",
        "project_root": str(other_project),
    }

    assert _gated(client.post("/code/query", json=body, headers=chief.headers))


@pytest.mark.parametrize(
    "target",
    [
        "a.py",
        "src/a.py",
        "src/../a.py",
        "OWN/src/a.py",
        "OWN\\src\\a.py",
        "OWN/",
        "OWN",
        "parse_result",
    ],
)
def test_a_code_query_target_inside_the_project_passes(client, project, target):
    chief = _chief("status", project)

    resp = _target(client, chief, project, target.replace("OWN", str(project)))

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _passed(resp)


def test_a_code_query_names_its_project_even_for_an_absolute_target(client, project):
    chief = _chief("status", project)
    body = {"op": "impact", "target": str(project / "a.py"), "scope": "(interactive)"}

    resp = client.post("/code/query", json=body, headers=chief.headers)

    assert _gated(resp)
    assert "project_root" in resp.get_json()["error"]


# --- a post names a file by `artifact_path` -----------------------------------------------
#
# An artifact row keeps the path it was given, and `GET /comms/artifacts/<id>/section` reads that
# file whole, so a chief that can name any path can read any file the server can.


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize(
    "fields",
    [
        {"artifact_path": "OTHER/secret.md"},
        {"artifact_path": "OTHER/secret.md", "type": "note"},
        {"artifact_path": "/etc/passwd"},
        {"artifact_path": "C:\\Users\\someone\\secret.md"},
        {"artifact_path": "pathly/features/x/PLAN.md"},
        {"artifact_path": "OWN/../proj-b/secret.md"},
        {"text": "report is at OTHER/secret.md"},
        {"text": "report is at pathly/features/x/PLAN.md"},
        {"artifact_path": "  ", "text": "report is at pathly/features/x/PLAN.md"},
    ],
    ids=lambda f: ",".join(f"{k}={v}"[:44] for k, v in f.items()),
)
def test_a_post_may_name_only_a_file_inside_its_project(
    client, project, other_project, tier, fields
):
    chief = _chief(tier, project)
    fields = {
        k: v.replace("OTHER", str(other_project)).replace("OWN", str(project))
        for k, v in fields.items()
    }

    resp = client.post(
        "/comms/post",
        json=_msg("artifact", **{"type": "artifact", **fields}),
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert _count("SELECT COUNT(*) FROM comms_artifacts") == 0


def test_a_post_of_a_file_inside_its_project_passes(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post",
        json=_msg(
            "artifact",
            text="the plan",
            artifact_path=str(project / "pathly" / "PLAN.md"),
        ),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _count("SELECT COUNT(*) FROM comms_artifacts") == 1


def test_a_note_that_mentions_a_path_is_not_an_artifact(client, project):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post",
        json=_msg("note", text="see pathly/features/x/PLAN.md"),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)


def test_context_refs_resolve_against_the_server_directory_unless_the_root_is_named(
    client, project
):
    chief = _chief("operator", project)
    refs = [{"artifact": "pathly/features/x/PLAN.md", "anchor": "goal"}]

    unnamed = client.post(
        "/comms/post", json=_msg("note", context_refs=refs), headers=chief.headers
    )
    named = client.post(
        "/comms/post",
        json=_msg("note", context_refs=refs, project_root=str(project)),
        headers=chief.headers,
    )

    assert _gated(unnamed)
    assert "project_root" in unnamed.get_json()["error"]
    assert named.status_code == 200, named.get_data(as_text=True)


# --- the table is complete, and says something about every route --------------------------


def _chief_reachable(app) -> set[tuple[str, str]]:
    """Every (rule, method) a chief token can get past the route table: the listed non-GET
    routes, and every GET that is not refused.
    """
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS, action_for

    found = set()
    for rule in app.url_map.iter_rules():
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            if method == "GET":
                if action_for(rule.rule, "GET", {}, {}, lambda _: False) is not None:
                    found.add((rule.rule, "GET"))
            elif (rule.rule, method) in ROUTE_ACTIONS:
                found.add((rule.rule, method))
    return found


def test_the_walk_finds_the_routes_a_chief_can_reach(app):
    reachable = _chief_reachable(app)

    assert {
        ("/comms", "GET"),
        ("/runs/<run_id>", "GET"),
        ("/db/stats", "GET"),
        ("/comms/post", "POST"),
        ("/code/query", "POST"),
        ("/runs/<run_id>/<action>", "POST"),
    } <= reachable
    assert ("/db/settings", "GET") not in reachable
    assert ("/events/spawn", "GET") not in reachable
    assert ("/db/query", "POST") not in reachable
    assert len(reachable) > 60


def test_every_route_a_chief_can_reach_says_which_fields_it_reads_as_a_project(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    missing = _chief_reachable(app) - set(ROUTE_FIELDS)

    assert not missing, (
        "a route the chief can reach has no entry in chief_fields.ROUTE_FIELDS "
        f"(list the project fields it reads, or say that it reads none): {sorted(missing)}"
    )


def test_the_field_table_lists_no_route_that_does_not_exist(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    stale = set(ROUTE_FIELDS) - _chief_reachable(app) - PLANNED

    assert (
        not stale
    ), f"the field table lists routes the chief cannot reach: {sorted(stale)}"


def test_an_entry_names_a_field_or_gives_a_reason(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    silent = [
        key
        for key, fields in ROUTE_FIELDS.items()
        if not fields.declared() and not fields.note.strip()
    ]

    assert silent == [], f"an entry that reads no project field must say why: {silent}"


def test_a_route_that_names_its_root_reads_one(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    for key, fields in ROUTE_FIELDS.items():
        if fields.names_root or fields.names_root_when:
            assert "project_root" in fields.roots, key


def test_every_route_that_starts_an_agent_in_a_directory_names_its_root():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS

    # `/runs/<run_id>/<action>` and the stops name a run or a board by id (ticket 14).
    starts_one = {
        rule
        for (rule, _), action in ROUTE_ACTIONS.items()
        if action == "run" and rule != "/runs/<run_id>/<action>"
    } | {rule for (rule, _) in ROUTE_ACTIONS if "decompose" in rule}
    names_root = {
        rule
        for (rule, method), f in ROUTE_FIELDS.items()
        if method != "GET" and f.names_root
    }

    assert names_root == starts_one | {"/code/query"}
    assert starts_one == {p for p, _ in NAMES_A_PROJECT}


def test_the_reads_that_name_their_root_are_the_ones_that_fall_back_to_another_project():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    names_root = {
        rule
        for (rule, method), f in ROUTE_FIELDS.items()
        if method == "GET" and f.names_root
    }

    assert names_root == set(NAMES_A_PROJECT_READS)


_FIELD_READ = re.compile(
    r"""(?:\bdata|\bbody|args|payload)\.get(?:list)?\(\s*["']([A-Za-z_]+)["']"""
)
_PROJECT_ISH = re.compile(r"root|scope|board|project|feature|path|target|topic|_id$")


def test_a_view_reads_no_project_ish_field_its_entry_does_not_name(app):
    """A tripwire, not a proof: it reads the view function's own source, not its helpers."""
    import inspect

    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    undeclared = {}
    for (rule_text, method), fields in ROUTE_FIELDS.items():
        for rule in app.url_map.iter_rules():
            if rule.rule != rule_text or method not in rule.methods:
                continue
            try:
                source = inspect.getsource(
                    inspect.unwrap(app.view_functions[rule.endpoint])
                )
            except (OSError, TypeError):
                continue
            read = {k for k in _FIELD_READ.findall(source) if _PROJECT_ISH.search(k)}
            if read - fields.declared():
                undeclared[(rule_text, method)] = sorted(read - fields.declared())

    assert undeclared == {}, f"views read fields the table does not name: {undeclared}"


def test_a_listed_non_get_route_reads_the_body_and_a_get_route_reads_the_query(app):
    """The table applies to the body of a POST and the query string of a GET: no listed POST view
    reads ``request.args`` and no GET view reads a JSON body.
    """
    import inspect

    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    crossed = []
    for rule_text, method in ROUTE_FIELDS:
        for rule in app.url_map.iter_rules():
            if rule.rule != rule_text or method not in rule.methods:
                continue
            try:
                source = inspect.getsource(
                    inspect.unwrap(app.view_functions[rule.endpoint])
                )
            except (OSError, TypeError):
                continue
            if method != "GET" and "request.args" in source:
                crossed.append((rule_text, method, "reads the query string"))
            if method == "GET" and re.search(
                r"get_json|read_json_body|request\.json|get_data", source
            ):
                crossed.append((rule_text, method, "reads a body"))

    assert crossed == []


def test_a_route_with_no_entry_is_refused_not_passed(client, project, monkeypatch):
    chief = _chief("status", project)
    assert client.get("/comms?feature=demo", headers=chief.headers).status_code == 200
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.chief_project.ROUTE_FIELDS", {}
    )

    resp = client.get("/comms?feature=demo", headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert resp.get_json()["action"] == "read"


# --- round 4: a name or a root a route takes as given -------------------------------------
#
# The earlier rounds bound the fields the views read as a project. The review of round 3 found
# three places where a route does more with a field than the table said: `retry` starts a run in
# the directory its own body names (and takes an empty one), `/comms/features/decompose` joins the
# `feature` into a path, and `/telemetry/trends` with no feature sums every project.

RETRY_FIELDS = {"flow": "team", "max_iterations": 3, "max_cost_usd": 1}


@pytest.fixture()
def finished_run(monkeypatch):
    """A finished run of the registry, and a record of the runs a retry starts."""
    from types import SimpleNamespace

    from pathly_orchestrator.supervisor import registry

    started_runs: list[dict] = []

    def fake_start_run(**kwargs):
        started_runs.append(kwargs)
        return SimpleNamespace(run_id="run-new-1")

    monkeypatch.setitem(
        registry._registry,
        "retry-topic",
        SimpleNamespace(run_id="run-own-1", status="done"),
    )
    monkeypatch.setattr("pathly_orchestrator.supervisor.api.start_run", fake_start_run)
    return started_runs


@pytest.mark.parametrize("value", ["absent", "", None, 0, False, [], {}], ids=repr)
def test_a_retry_that_names_no_project_is_refused(client, project, finished_run, value):
    chief = _chief("operator", project)
    body = dict(RETRY_FIELDS)
    if value != "absent":
        body["project_root"] = value

    resp = client.post("/runs/run-own-1/retry", json=body, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]
    assert finished_run == []


def test_a_retry_that_names_its_own_project_starts_the_run_there(
    client, project, finished_run
):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs/run-own-1/retry",
        json={**RETRY_FIELDS, "project_root": str(project)},
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert [c["project_root"] for c in finished_run] == [str(project)]


def test_a_retry_in_another_project_is_refused(
    client, project, other_project, finished_run
):
    chief = _chief("operator", project)

    resp = client.post(
        "/runs/run-own-1/retry",
        json={**RETRY_FIELDS, "project_root": str(other_project)},
        headers=chief.headers,
    )

    assert _gated(resp)
    assert finished_run == []


@pytest.mark.parametrize("verb", ["pause", "resume", "advance", "reroute"])
def test_the_other_run_verbs_need_no_root(client, project, verb):
    """They act on a run's own state, not on a directory the body names."""
    chief = _chief("operator", project)

    resp = client.post(f"/runs/x/{verb}", json={}, headers=chief.headers)

    assert _passed(resp), resp.get_data(as_text=True)


# `/comms/features/decompose` makes `<project_root>/pathly/features/<feature>` and hands the
# string to the run as its storage path, so the feature is a folder name.

RIGORS = ["light", "full", "consultation"]
ROUTE_REFUSES = [
    "../../../proj-b/pathly/features/planted",
    "../../../proj-b/planted",
    "../planted",
    "a/../../planted",
    "..",
    "OTHER/planted",
    "a\\b",
    "c:x",
]
ONLY_THE_GATE_REFUSES = ["sub/dir", "./x", " ../x ", " .. "]


@pytest.fixture()
def consultations(monkeypatch):
    """Record the feature-consultation runs the route starts, instead of starting any."""
    from types import SimpleNamespace

    calls: list[dict] = []

    def fake_start_run(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(run_id="consult-1")

    monkeypatch.setattr("pathly_orchestrator.supervisor.api.start_run", fake_start_run)
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.goal_executor._reset_fsm_state_for_flow",
        lambda *a, **k: None,
    )
    return calls


def _feature_body(feature, rigor, project) -> dict:
    return {"feature": feature, "rigor": rigor, "project_root": str(project)}


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("rigor", RIGORS)
@pytest.mark.parametrize("feature", [*ROUTE_REFUSES, *ONLY_THE_GATE_REFUSES])
def test_a_feature_name_that_is_a_path_is_refused_to_a_chief(
    client, project, other_project, started, consultations, tier, rigor, feature
):
    chief = _chief(tier, project)
    feature = feature.replace("OTHER", str(other_project))

    resp = client.post(
        "/comms/features/decompose",
        json=_feature_body(feature, rigor, project),
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "feature" in resp.get_json()["error"]
    assert started == [] and consultations == []
    assert list(other_project.rglob("*")) == []


@pytest.mark.parametrize("value", [["x"], 7, {"a": 1}])
def test_a_feature_that_is_not_a_string_is_refused_to_a_chief(client, project, value):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/features/decompose",
        json=_feature_body(value, "light", project),
        headers=chief.headers,
    )

    assert _gated(resp)


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("rigor", RIGORS)
@pytest.mark.parametrize("feature", ["export-csv", "feat_1", "Q3 plan", ".hidden"])
def test_a_plain_feature_name_passes_the_gate(
    client, project, started, consultations, tier, rigor, feature
):
    chief = _chief(tier, project)

    resp = client.post(
        "/comms/features/decompose",
        json=_feature_body(feature, rigor, project),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _passed(resp)


@pytest.mark.parametrize("rigor", RIGORS)
@pytest.mark.parametrize("feature", ROUTE_REFUSES)
def test_the_route_plants_nothing_for_a_feature_that_is_a_path(
    client, project, other_project, started, consultations, rigor, feature
):
    """The route itself, with no token: a feature name must not leave the project."""
    feature = feature.replace("OTHER", str(other_project))

    resp = client.post(
        "/comms/features/decompose", json=_feature_body(feature, rigor, project)
    )

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert resp.get_json()["reason"] == "invalid_feature"
    assert started == [] and consultations == []
    assert list(other_project.rglob("*")) == []
    assert not (project / "pathly" / "planted").exists()


@pytest.mark.parametrize("rigor", RIGORS)
def test_the_route_still_makes_the_folder_of_a_plain_feature(
    client, project, started, consultations, rigor
):
    resp = client.post(
        "/comms/features/decompose", json=_feature_body("export-csv", rigor, project)
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert (project / "pathly" / "features" / "export-csv").is_dir()


# `/comms/run` of an evaluator on a feature or global board saves a reply that posted no
# BOARD_EVAL artifact to `<project_root>/pathly/features/<scope>/artifacts/`, so its scope is a
# folder name there too (a project board's scope is the root itself, and is bound as such).


def _wait_for_the_board_run(board: str, scope: str) -> None:
    import time

    from pathly_orchestrator.supervisor import board_lock

    deadline = time.monotonic() + 10
    while board_lock.holder(board, scope) is not None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert board_lock.holder(board, scope) is None, "the board run never finished"


@pytest.fixture()
def evaluator_reply(monkeypatch):
    """Spawn no agent; the evaluator's run ends at once with a reply and no artifact."""
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.board_run._default_spawn",
        lambda **kwargs: {"result": "a real analysis of the board"},
    )
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.sse._broadcast_runner", lambda *a, **k: None
    )


def _evaluate(client, project, scope, headers=None):
    return client.post(
        "/comms/run",
        json={
            "board": "global",
            "scope": scope,
            "mode": "evaluator",
            "project_root": str(project),
        },
        headers=headers or {},
    )


def test_the_route_saves_an_evaluation_inside_the_project(
    client, project, evaluator_reply
):
    resp = _evaluate(client, project, "demo-board")
    assert resp.status_code == 200, resp.get_data(as_text=True)
    _wait_for_the_board_run("global", "demo-board")

    saved = project / "pathly" / "features" / "demo-board" / "artifacts"
    assert (saved / "BOARD_EVAL.md").is_file()


def test_the_route_saves_no_evaluation_outside_the_project(
    client, project, other_project, evaluator_reply
):
    scope = "../../../proj-b/planted"

    resp = _evaluate(client, project, scope)
    assert resp.status_code == 200, resp.get_data(as_text=True)
    _wait_for_the_board_run("global", scope)

    assert list(other_project.rglob("*")) == []


@pytest.mark.parametrize("scope", ["../../../proj-b/planted", "sub/../../x", "a\\b"])
def test_a_chief_names_a_folder_name_as_the_scope_of_a_global_board_run(
    client, project, other_project, evaluator_reply, scope
):
    chief = _chief("operator", project)

    resp = _evaluate(client, project, scope, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "scope" in resp.get_json()["error"]
    assert list(other_project.rglob("*")) == []


def test_a_project_board_run_names_the_root_as_its_scope_still(
    client, project, started
):
    chief = _chief("operator", project)
    body = {
        "board": "project",
        "scope": str(project),
        "mode": "single-agent",
        "project_root": str(project),
    }

    resp = client.post("/comms/run", json=body, headers=chief.headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert len(started) == 1


# `/telemetry/trends` with a feature sums that feature across every project; without one it sums
# every project's cost unless `project_root` narrows it.


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize("feature", ["", "   "])
def test_trends_without_a_feature_must_name_the_project(
    client, project, other_project, tier, feature
):
    chief = _chief(tier, project)

    unnamed = client.get(
        "/telemetry/trends", query_string={"feature": feature}, headers=chief.headers
    )
    other = client.get(
        "/telemetry/trends",
        query_string={"feature": feature, "project_root": str(other_project)},
        headers=chief.headers,
    )
    own = client.get(
        "/telemetry/trends",
        query_string={"feature": feature, "project_root": str(project)},
        headers=chief.headers,
    )

    assert _gated(unnamed), (unnamed.status_code, unnamed.get_data(as_text=True)[:200])
    assert "project_root" in unnamed.get_json()["error"]
    assert _gated(other)
    assert _passed(own), (own.status_code, own.get_data(as_text=True)[:200])


def test_trends_of_a_named_feature_stay_fleet_wide_and_say_so(client, project):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    chief = _chief("status", project)

    resp = client.get(
        "/telemetry/trends", query_string={"feature": "demo"}, headers=chief.headers
    )

    assert _passed(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    entry = ROUTE_FIELDS[("/telemetry/trends", "GET")]
    assert "feature" in entry.unbound
    assert "every project" in entry.note


def test_db_stats_says_its_counts_are_global():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    note = ROUTE_FIELDS[("/db/stats", "GET")].note

    for word in ("features", "events", "invocations", "global"):
        assert word in note, note


# The `unbound` entries list what the gate really leaves to the caller. A feature that a query
# filters by `project_root` as well is bound by the root the gate checks.

FEATURE_UNDER_THE_ROOT = [
    "/db/features/<feature>/agents",
    "/db/features/<feature>/events",
    "/db/features/<feature>/otel",
    "/db/features/<feature>/runs",
    "/api/features/<feature>/artifacts",
    "/api/features/<feature>/events",
    "/api/features/<feature>/invocations",
    "/api/features/<feature>/metrics",
    "/api/traces",
    "/flows/stage-config",
    "/comms/scope",
    "/db/rollup",
]


@pytest.mark.parametrize("rule", FEATURE_UNDER_THE_ROOT)
def test_a_feature_filtered_by_the_root_as_well_is_not_listed_unbound(rule):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    entry = ROUTE_FIELDS[(rule, "GET")]

    assert "feature" not in entry.unbound
    assert "project_root" in entry.roots
