"""chief-agent 08 (round 8): a file a chief names is inside its project once symlinks are followed.

The gate compared a chief's ``artifact_path`` and its ``/code/query`` ``target`` with the
project root as text, so a symlink inside project A that points at project B passed, and the
server then opened B's file (``GET /comms/artifacts`` showed a chief B's heading names). The
gate now also resolves the path the way ``open`` does (``hydrate_helpers.inside_root``, the
check the by-id section read already makes) and refuses one that leaves the project.
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


@pytest.fixture()
def linked(project, other_project):
    """Project A holds links: to project B, to a file of B, to a folder of A, and one that
    climbs out through ``..``.
    """
    plan = other_project / "pathly" / "features" / "demo" / "PLAN.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# Secret\n\n## hidden-heading\n")
    (other_project / "sub").mkdir()
    (project / "inner").mkdir()
    (project / "inner" / "a.py").write_text("x = 1\n")
    (project / "link").symlink_to(other_project, target_is_directory=True)
    (project / "sublink").symlink_to(other_project / "sub", target_is_directory=True)
    (project / "file_link.md").symlink_to(plan)
    (project / "inner_link").symlink_to(project / "inner", target_is_directory=True)
    return project


OUTSIDE = [
    "OWN/link/pathly/features/demo/PLAN.md",
    "OWN/link",
    "OWN/file_link.md",
    "OWN/sublink/x.md",
    # The text check collapses this to OWN/x.md; the file system resolves ``sublink`` first,
    # so ``..`` is the parent of project B's ``sub`` folder.
    "OWN/sublink/../x.md",
]
INSIDE = ["OWN/inner_link/a.py", "OWN/inner/a.py", "OWN/new/PLAN.md"]


def _fill(text: str, project) -> str:
    return text.replace("OWN", str(project))


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("path", OUTSIDE)
def test_an_artifact_path_through_a_symlink_out_of_the_project_is_refused(
    client, linked, tier, path
):
    chief = _chief(tier, linked)

    resp = client.post(
        "/comms/post",
        json=_msg("artifact", artifact_path=_fill(path, linked)),
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "inside its project" in resp.get_json()["error"]
    assert _count("SELECT COUNT(*) FROM comms_artifacts") == 0


@pytest.mark.parametrize("tier", ["planner", "operator"])
@pytest.mark.parametrize("path", INSIDE)
def test_an_artifact_path_through_a_symlink_inside_the_project_passes(
    client, linked, tier, path
):
    chief = _chief(tier, linked)

    resp = client.post(
        "/comms/post",
        json=_msg("artifact", artifact_path=_fill(path, linked)),
        headers=chief.headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _count("SELECT COUNT(*) FROM comms_artifacts") == 1


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize(
    "target",
    [
        "link/pathly/features/demo/PLAN.md",
        "link",
        "file_link.md",
        "sublink/../x.md",
        *OUTSIDE,
    ],
)
def test_a_code_query_target_through_a_symlink_out_of_the_project_is_refused(
    client, linked, tier, target
):
    chief = _chief(tier, linked)

    resp = _code_query(
        client, chief, linked, target=_fill(target, linked), scope="(interactive)"
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "inside its project" in resp.get_json()["error"]


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize(
    "target", ["inner_link/a.py", "inner/a.py", "missing.py", "parse_result", *INSIDE]
)
def test_a_code_query_target_through_a_symlink_inside_the_project_passes(
    client, linked, tier, target
):
    chief = _chief(tier, linked)

    resp = _code_query(
        client, chief, linked, target=_fill(target, linked), scope="(interactive)"
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _passed(resp)


def test_a_project_reached_through_a_symlinked_root_keeps_its_own_files(
    client, project, tmp_path
):
    """The session's root is a symlink to the project (macOS ``/var`` is one): both sides of
    the check are resolved, so a file under the root the chief was opened with is still its own.
    """
    (project / "src").mkdir()
    (project / "src" / "a.py").write_text("x = 1\n")
    root = tmp_path / "via-link"
    root.symlink_to(project, target_is_directory=True)
    chief = _chief("operator", root)

    query = _code_query(client, chief, root, target="src/a.py", scope="(interactive)")
    absolute = _code_query(
        client, chief, root, target=str(root / "src" / "a.py"), scope="(interactive)"
    )
    post = client.post(
        "/comms/post",
        json=_msg("artifact", artifact_path=str(root / "pathly" / "PLAN.md")),
        headers=chief.headers,
    )

    assert _passed(query) and query.status_code == 200, query.get_data(as_text=True)
    assert _passed(absolute) and absolute.status_code == 200
    assert post.status_code == 200, post.get_data(as_text=True)
