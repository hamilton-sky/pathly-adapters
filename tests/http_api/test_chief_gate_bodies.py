"""chief-agent 08: the gate reads the body the way the route will.

A body in any encoding a route understands (UTF-8, a BOM, UTF-16, UTF-32, cp1252) is
classed and bound by the gate as the route will read it, and the route still gets it
whole.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from chief_cite_support import Session

from chief_gate_support import (
    ENCODINGS,
    _chief,
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

WITH_PLAIN = [None, *ENCODINGS]


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
    chief = Session("operator", project)
    body = {"topic": "t", "cite": chief.type("a"), "project_root": str(other_project)}

    resp = _send(client, "/runner/agent-answer", body, encoding, chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert resp.get_json()["error"] == "that is not this chief's project"


@pytest.mark.parametrize("encoding", WITH_PLAIN)
def test_agent_answer_of_its_own_project_reaches_the_route(client, project, encoding):
    chief = Session("operator", project)
    body = {"topic": "t", "cite": chief.type("a"), "project_root": str(project)}

    resp = _send(client, "/runner/agent-answer", body, encoding, chief.headers)

    # The route read the topic from the body: no run has that topic. (A chief cites a message
    # it did not word: the cite rule of ticket 10 refuses a body that carries an `answer`.)
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
