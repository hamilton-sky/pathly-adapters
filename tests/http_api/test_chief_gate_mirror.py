"""chief-agent 08 (round 5): a request string that becomes part of a filesystem path.

The board mirror treats any scope with a ``/`` as a project root and writes
``<scope>/pathly/project/BOARD.json``, whatever board the row was posted to, so a chief on one
project could plant files in another through the scope of a feature-board post. The same class
is a goal ``slug`` the server later joins into ``pathly/features/<f>/goals/<slug>``. These tests
hold the class, not only the reported route: on a board other than ``project`` every route that
reads a scope refuses a scope that is a path, and a slug is one folder name.
"""

from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from werkzeug.datastructures import MultiDict

from chief_gate_support import (
    _chief,
    _count,
    _gated,
    _msg,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
    started,
)

# Scopes that are a path. OWN and OTHER stand for the chief's project root and another
# project's. A relative one is read against the working directory, which the tests put in the
# chief's project, so `../proj-b` names the other project from there.
PATH_SCOPES = [
    "OTHER",
    "OWN/../proj-b",
    "../proj-b",
    "sub/dir",
    "C:/other/proj",
    "C:\\other\\proj",
    "a\\b",
    "..",
    ".",
]
PLAIN_SCOPES = ["demo", "Q3 plan", "café-ü", "v1.2.3", ".hidden"]


def _fill(text: str, project, other_project) -> str:
    return text.replace("OTHER", str(other_project)).replace("OWN", str(project))


def _settle_mirror() -> None:
    """Let the debounced board-mirror flusher write whatever it was asked to.

    The flusher runs on its own thread every ``DEBOUNCE_SECONDS``: flush here, wait out one
    tick (a write the thread took first finishes meanwhile), and flush again.
    """
    from pathly_orchestrator import board_mirror
    from pathly_orchestrator.db.connection import get_db

    board_mirror.flush_dirty(get_db())
    time.sleep(board_mirror.DEBOUNCE_SECONDS + 0.3)
    board_mirror.flush_dirty(get_db())


@pytest.fixture()
def flow_started(monkeypatch):
    """Record the FSM runs ``POST /runs`` starts, instead of starting any."""
    calls: list[dict] = []

    def fake_start_run(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(run_id="flow-1")

    monkeypatch.setattr("pathly_orchestrator.supervisor.api.start_run", fake_start_run)
    return calls


# --- the reported route: a post --------------------------------------------------------------


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("board", ["feature", "global", None])
@pytest.mark.parametrize("scope", PATH_SCOPES)
def test_a_post_cannot_name_a_path_as_the_scope_of_a_feature_or_global_board(
    client, project, other_project, monkeypatch, tier, board, scope
):
    monkeypatch.chdir(project)
    chief = _chief(tier, project)
    fields = {"scope": _fill(scope, project, other_project)}
    if board:
        fields["board"] = board

    resp = client.post(
        "/comms/post", json=_msg("note", **fields), headers=chief.headers
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert _count("SELECT COUNT(*) FROM comms_messages") == 0


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("scope", ["OTHER", "../proj-b", "sub/dir", "C:/other/proj"])
def test_a_post_whose_scope_falls_back_to_a_feature_that_is_a_path_is_refused(
    client, project, other_project, monkeypatch, tier, scope
):
    monkeypatch.chdir(project)
    chief = _chief(tier, project)
    body = _msg("note", feature=_fill(scope, project, other_project))

    resp = client.post("/comms/post", json=body, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert _count("SELECT COUNT(*) FROM comms_messages") == 0


# What the finding actually reproduced: files in the other project's tree. The mirror writes on
# its own thread, so these wait for it.


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize(
    "scope", ["OTHER", "OWN/../proj-b", "../proj-b", "C:/other/proj"]
)
def test_a_chief_plants_no_file_in_another_project_through_the_scope_of_a_post(
    client, project, other_project, monkeypatch, tier, scope
):
    monkeypatch.chdir(project)
    chief = _chief(tier, project)
    fields = {"board": "feature", "scope": _fill(scope, project, other_project)}

    resp = client.post(
        "/comms/post", json=_msg("note", **fields), headers=chief.headers
    )
    _settle_mirror()

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert list(other_project.rglob("*")) == []
    assert list(project.rglob("*")) == []


@pytest.mark.parametrize("scope", PLAIN_SCOPES)
def test_a_post_to_a_feature_board_named_by_a_plain_name_still_passes(
    client, project, scope
):
    chief = _chief("operator", project)

    resp = client.post(
        "/comms/post",
        json=_msg("note", board="feature", scope=scope),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE scope = ?", scope) == 1


@pytest.mark.parametrize("scope", ["OWN/../proj-b", "../proj-b"])
def test_the_route_itself_plants_nothing_for_a_scope_that_is_a_path(
    client, project, other_project, monkeypatch, scope
):
    """No token: a human or an agent without one. The gate does not see the call, so the
    board mirror is what keeps the other project's tree untouched."""
    monkeypatch.chdir(project)
    body = _msg("note", board="feature", scope=_fill(scope, project, other_project))

    resp = client.post("/comms/post", json=body)
    _settle_mirror()

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert list(other_project.rglob("*")) == []


# --- the other route the review named: a run on a global or feature board --------------------


@pytest.mark.parametrize("kind", ["single", "evaluator", "flow"])
@pytest.mark.parametrize("board", ["feature", "global", None])
@pytest.mark.parametrize("scope", PATH_SCOPES)
def test_a_run_cannot_name_a_path_as_the_scope_of_a_feature_or_global_board(
    client,
    project,
    other_project,
    started,
    flow_started,
    monkeypatch,
    kind,
    board,
    scope,
):
    monkeypatch.chdir(project)
    chief = _chief("operator", project)
    body = {
        "kind": kind,
        "scope": _fill(scope, project, other_project),
        "flow": "team",
        "project_root": str(project),
    }
    if board:
        body["board"] = board

    resp = client.post("/runs", json=body, headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert started == [] and flow_started == []


@pytest.mark.parametrize("board", ["global", "feature"])
@pytest.mark.parametrize("scope", ["OTHER", "OWN/../proj-b", "../proj-b"])
def test_a_chief_plants_no_file_in_another_project_through_the_scope_of_a_run(
    client, project, other_project, started, monkeypatch, board, scope
):
    monkeypatch.chdir(project)
    chief = _chief("operator", project)
    body = {
        "kind": "single",
        "board": board,
        "scope": _fill(scope, project, other_project),
        "project_root": str(project),
    }

    resp = client.post("/runs", json=body, headers=chief.headers)
    _settle_mirror()

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert started == []
    assert list(other_project.rglob("*")) == []
    assert list(project.rglob("*")) == []


# --- the class: every route that reads a scope -----------------------------------------------


def _scope_reads():
    """Every (rule, method, ScopeRead) of the field table that is not the project board's."""
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    return [
        pytest.param(rule, method, read, id=f"{method} {rule} {read.keys}")
        for (rule, method), fields in ROUTE_FIELDS.items()
        for read in fields.scopes
        if read.board != "project"
    ]


def _refusal(rule, method, project, **fields):
    """The gate's project refusal for a call of ``rule`` with ``fields`` (None: not refused).

    The gate's own function, not an HTTP call: a call it passed would reach the real route,
    which for a run route starts an agent.
    """
    from pathly_orchestrator.http_server.chief_project import project_refusal

    session = {"project_root": str(project)}
    body = {} if method == "GET" else dict(fields)
    args = MultiDict(fields if method == "GET" else {})
    return project_refusal(rule, method, session, body, args, {})


def _boards_of(read):
    return ("feature", "global", None) if read.board_key else (None,)


def test_the_walk_reaches_the_scope_reads_of_the_post_and_run_routes():
    rules = {p.values[0] for p in _scope_reads()}

    assert {"/comms/post", "/runs", "/comms/search", "/comms"} <= rules
    assert {"/comms/run", "/comms/features/decompose"} <= rules


@pytest.mark.parametrize("rule,method,read", _scope_reads())
@pytest.mark.parametrize("scope", PATH_SCOPES)
def test_a_scope_that_is_a_path_is_refused_on_every_board_but_the_project_board(
    project, other_project, rule, method, read, scope
):
    for board in _boards_of(read):
        fields = {
            "project_root": str(project),
            read.keys[0]: _fill(scope, project, other_project),
        }
        if board:
            fields[read.board_key] = board

        refusal = _refusal(rule, method, project, **fields)

        assert refusal is not None, (rule, method, board, scope)


@pytest.mark.parametrize("rule,method,read", _scope_reads())
@pytest.mark.parametrize("scope", PLAIN_SCOPES)
def test_a_plain_name_is_not_refused_as_a_scope_on_any_route(
    project, rule, method, read, scope
):
    for board in _boards_of(read):
        fields = {"project_root": str(project), read.keys[0]: scope}
        if board:
            fields[read.board_key] = board

        refusal = _refusal(rule, method, project, **fields)

        assert refusal is None, (rule, method, board, scope, refusal)


# --- a stored slug: the folder a goal run is given -------------------------------------------

SLUG_PATHS = [
    "../../../../../proj-b/planted",
    "../x",
    "a/b",
    "/abs/x",
    "a\\b",
    "..",
    "c:x",
]


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("slug", SLUG_PATHS)
def test_a_goal_slug_that_is_a_path_is_refused_to_a_chief(client, project, tier, slug):
    chief = _chief(tier, project)

    resp = client.post(
        "/comms/post", json=_msg("goal", slug=slug), headers=chief.headers
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "slug" in resp.get_json()["error"]
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE type = 'goal'") == 0


@pytest.mark.parametrize("slug", ["export-csv-1a2b3c4d", "Q3 plan", ".hidden", "café"])
def test_a_plain_goal_slug_passes(client, project, slug):
    chief = _chief("planner", project)

    resp = client.post(
        "/comms/post", json=_msg("goal", slug=slug), headers=chief.headers
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE slug = ?", slug) == 1


@pytest.mark.parametrize("slug", SLUG_PATHS)
def test_a_goal_run_plants_nothing_for_a_stored_slug_that_is_a_path(
    project, other_project, slug
):
    """The server side of the same class: whoever stored the slug, the goal's home is made
    from a safe one, so a goal run makes no folder outside the project.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_messages import post_message
    from pathly_orchestrator.supervisor.slug import resolve_goal_home

    goal_id = post_message(
        get_db(),
        board="feature",
        scope="demo",
        from_agent="chief",
        type="goal",
        text="Ship the export",
        slug=slug,
    )

    got, home = resolve_goal_home(str(project), "feature", "demo", goal_id)

    assert got != slug and not any(c in got for c in "/\\:")
    assert home is not None and project in Path(home).parents
    assert list(other_project.rglob("*")) == []
    assert not (project.parent / "planted").exists()
