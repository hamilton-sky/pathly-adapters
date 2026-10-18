"""chief-agent 08: reads of a board are bound by the board and scope they name.

``/comms/search``, the board lists and the other board reads refuse another project's
board and pass the chief's own or a feature board.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chief_gate_support import (
    TIERS,
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
)


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
