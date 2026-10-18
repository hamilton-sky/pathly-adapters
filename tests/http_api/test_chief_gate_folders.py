"""chief-agent 08: a name a route makes a folder of is one folder name.

``/comms/features/decompose`` joins ``feature``, and ``/comms/run`` of an evaluator on a
feature or global board joins ``scope``, into ``<project_root>/pathly/features/``.
"""

from __future__ import annotations

import pytest

from chief_gate_support import (
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
    started,
)

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
