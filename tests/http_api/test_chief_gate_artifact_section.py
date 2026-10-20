"""chief-agent 08 (round 6): the section of an artifact read by id stays inside the named project.

``GET /comms/artifacts/<id>/section`` reads the path stored on the artifact's row. A chief does
not choose that path (another writer posted the row), but it chooses the project root it names,
so the stored path has to lie under that root.
"""

from __future__ import annotations

import pytest

from chief_gate_support import (
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)

BODY = "# Secret\n\nthe text of the file\n"


def _artifact(client, path) -> str:
    """Post an artifact message that stores ``path`` (no token: a human), return its artifact id."""
    resp = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "human",
            "type": "artifact",
            "text": "a file",
            "artifact_path": str(path),
            "artifact_type": "md",
        },
    )
    assert resp.status_code == 200, resp.get_data(as_text=True)
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute(
            "SELECT id FROM comms_artifacts WHERE message_id=?",
            (resp.get_json()["message_id"],),
        )
        .fetchone()
    )
    return row["id"]


def _section(client, artifact_id, root=None, headers=None, **query):
    if root is not None:
        query["project_root"] = str(root)
    return client.get(
        f"/comms/artifacts/{artifact_id}/section",
        query_string=query,
        headers=headers or {},
    )


@pytest.mark.parametrize("tier", ["status", "planner", "operator"])
def test_a_chief_does_not_read_a_file_of_another_project_through_an_artifact_id(
    client, project, other_project, tier
):
    secret = other_project / "secret.md"
    secret.write_text(BODY)
    artifact_id = _artifact(client, secret)
    chief = _chief(tier, project)

    resp = _section(client, artifact_id, project, chief.headers)

    assert resp.status_code != 200, resp.get_data(as_text=True)
    assert "the text of the file" not in resp.get_data(as_text=True)


@pytest.mark.parametrize("anchor", [None, "secret"])
def test_the_section_route_reads_no_file_outside_the_root_it_is_given(
    client, project, other_project, anchor
):
    """The route itself, with no token: a root named on the request bounds the stored path."""
    secret = other_project / "secret.md"
    secret.write_text(BODY)
    artifact_id = _artifact(client, secret)

    extra = {"anchor": anchor} if anchor else {}
    resp = _section(client, artifact_id, project, **extra)

    assert resp.status_code != 200, resp.get_data(as_text=True)
    assert "the text of the file" not in resp.get_data(as_text=True)


def test_a_chief_still_reads_a_file_of_its_own_project_through_an_artifact_id(
    client, project
):
    mine = project / "mine.md"
    mine.write_text(BODY)
    artifact_id = _artifact(client, mine)
    chief = _chief("status", project)

    resp = _section(client, artifact_id, project, chief.headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert "the text of the file" in resp.get_json()["text"]


def test_a_chief_names_its_root_to_read_an_artifact_by_id(client, project):
    mine = project / "mine.md"
    mine.write_text(BODY)
    artifact_id = _artifact(client, mine)
    chief = _chief("status", project)

    resp = _section(client, artifact_id, None, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert "project_root" in resp.get_json()["error"]


def test_a_caller_that_names_no_root_still_reads_by_id(client, other_project):
    """Studio and the agents that name no root read the stored path as before."""
    elsewhere = other_project / "secret.md"
    elsewhere.write_text(BODY)
    artifact_id = _artifact(client, elsewhere)

    resp = _section(client, artifact_id)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert "the text of the file" in resp.get_json()["text"]
