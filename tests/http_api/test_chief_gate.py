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

import os
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
        json={"mode": "planner", "prompt_override": "", "stage_overrides": {}},
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
        json={**base, "stage_overrides": {"PLANNING": "x"}, "prompt_override": "y"},
        headers=chief.headers,
    )

    assert _passed(resp), resp.get_data(as_text=True)


def test_operator_passes_the_gate_on_a_run_start(client, project):
    chief = _chief("operator", project)

    resp = client.post("/runs", json={"kind": "bogus"}, headers=chief.headers)

    assert resp.status_code == 400
    assert _passed(resp)


# --- unlisted routes are refused to every tier --------------------------------------------

UNLISTED = [
    ("post", "/db/query", {"sql": "SELECT 1"}),
    ("post", "/chief/open", {"engine": "claude"}),
    ("post", "/chief/close", {}),
    ("post", "/chief/human-messages", {"text": "x"}),
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
        ("/code/query", {}),
    ],
)
def test_a_status_chief_may_call_the_read_routes(client, project, path, body):
    chief = _chief("status", project)

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
    resp = client.post(f"/runs/x/{verb}", json={}, headers=operator.headers)
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
