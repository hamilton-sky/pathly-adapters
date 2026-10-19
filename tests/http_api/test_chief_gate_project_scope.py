"""chief-agent 08: a board named by ``scope`` is bound to the chief's project.

A post, a run, a decompose override and a code query that log to the project board must
name this project in ``scope``; a feature board is not bound by it.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from chief_gate_support import (
    ENCODINGS,
    _chief,
    _code_query,
    _count,
    _gated,
    _msg,
    _no_code_backend,
    _no_reindex,
    _passed,
    _send,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
    started,
)

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
@pytest.mark.parametrize("windows", [False, True], ids=["posix host", "windows host"])
def test_a_project_board_post_to_its_own_scope_passes(
    client, project, spelling, windows, monkeypatch
):
    """The scope is the project's root, and a backslash spells it only on a Windows host (on
    any other it is a different board, which the gate refuses as not the chief's own).
    """
    monkeypatch.setattr(
        "pathly_orchestrator.scope_names.host_is_windows",
        lambda: windows,
        raising=False,
    )
    root = project.as_posix()
    chief = _chief("operator", PurePosixPath(root))
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

    if spelling == "backslashes" and not windows:
        assert _gated(resp), resp.get_data(as_text=True)
    else:
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
