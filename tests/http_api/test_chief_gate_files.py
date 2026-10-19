"""chief-agent 08: a file a chief names must be inside its project.

The ``/code/query`` target, an ``artifact_path`` on a post and the ``context_refs`` a
task names are files the server will read.
"""

from __future__ import annotations

import pytest

from chief_gate_support import (
    TIERS,
    _chief,
    _code_query,
    _count,
    _gated,
    _msg,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)

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


@pytest.mark.parametrize("windows", [False, True], ids=["posix host", "windows host"])
def test_a_code_query_target_with_backslashes_is_the_projects_on_windows_only(
    client, project, windows, monkeypatch
):
    """A backslash separates only on a Windows host. On any other host the route opens the raw
    string, where ``proj-a\\src\\a.py`` is one file name in the folder above the project, so
    the gate refuses it (round 7); it used to read it as ``proj-a/src/a.py``.
    """
    monkeypatch.setattr(
        "pathly_orchestrator.scope_names.host_is_windows",
        lambda: windows,
        raising=False,
    )
    chief = _chief("status", project)

    resp = _target(client, chief, project, str(project) + "\\src\\a.py")

    if windows:
        assert resp.status_code == 200, resp.get_data(as_text=True)
        assert _passed(resp)
    else:
        assert _gated(resp), resp.get_data(as_text=True)


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
