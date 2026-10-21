"""chief-agent 08 (round 6): a chief sends only the keys its route's entry lists.

``ROUTE_FIELDS`` gives each route the complete list of body keys (or query keys, for a GET) a
chief may send. A key the entry does not list is refused with 403 naming it, so a field a route
reads and nobody declared (the ``flow`` of a goal run, the ``skill`` of a board run) is never
reached by a chief by accident.
"""

from __future__ import annotations

import pytest

from chief_gate_support import (
    _chief,
    _gated,
    _msg,
    _no_code_backend,
    _no_reindex,
    _passed,
    _streams_do_not_block,
    app,
    client,
    project,
    started,
)

UNKNOWN = "zz_undeclared"

# (method, path, a valid request, a key to add). Every route here is one an operator may call.
POSTS = [
    ("/comms/post", {"feature": "demo", "from": "chief", "type": "note", "text": "hi"}),
    ("/comms/search", {"feature": "demo", "query": "hello"}),
    ("/comms/goals/run", {"goal_id": "x"}),
    ("/comms/goals/decompose", {"goal_id": "x"}),
    ("/comms/features/decompose", {"feature": "demo", "rigor": "light"}),
    ("/comms/project/decompose", {"rigor": "light"}),
    ("/comms/run", {"scope": "demo"}),
    ("/comms/tasks/run", {"message_id": "x"}),
    ("/comms/acknowledge", {"message_id": "x", "agent": "chief"}),
    ("/comms/answer", {"question_id": "x", "answer": "yes"}),
    ("/comms/supersede", {"old_id": "x", "new_id": "y"}),
    ("/comms/directives", {"to_agent": "*", "text": "no new dependencies"}),
    ("/runs", {"kind": "single", "scope": "demo"}),
    ("/code/query", {"op": "impact", "target": "a.py", "role": "architect"}),
]
GETS = [
    "/comms?feature=demo",
    "/comms/tasks?feature=demo",
    "/comms/goals?feature=demo",
    "/runs",
    "/db/stats",
    "/db/features",
    "/status",
    "/comms/scope?feature=demo",
    "/skills/prompts",
    "/flows",
]


def _with_root(body: dict, project) -> dict:
    return {**body, "project_root": str(project)}


@pytest.mark.parametrize("path,body", POSTS)
def test_a_chief_cannot_send_a_body_key_its_route_does_not_list(
    client, project, started, path, body
):
    chief = _chief("operator", project)

    resp = client.post(
        path, json={**_with_root(body, project), UNKNOWN: 1}, headers=chief.headers
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert UNKNOWN in resp.get_json()["error"]


@pytest.mark.parametrize("path", GETS)
def test_a_chief_cannot_send_a_query_key_its_route_does_not_list(client, project, path):
    chief = _chief("status", project)
    sep = "&" if "?" in path else "?"

    resp = client.get(
        f"{path}{sep}project_root={project}&{UNKNOWN}=1", headers=chief.headers
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert UNKNOWN in resp.get_json()["error"]


@pytest.mark.parametrize(
    "path,key",
    [
        ("/comms/goals/run", "flow"),
        ("/comms/goals/run", "ability_ids"),
        ("/comms/run", "system_prompt"),
        ("/comms/run", "interactive"),
        ("/comms/post", "summary_backend"),
        ("/runs", "ability_ids"),
    ],
)
def test_a_key_the_route_reads_and_no_chief_flow_needs_is_not_listed(
    client, project, started, path, key
):
    bodies = dict(POSTS)
    chief = _chief("operator", project)

    resp = client.post(
        path,
        json={**_with_root(bodies[path], project), key: "x"},
        headers=chief.headers,
    )

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert key in resp.get_json()["error"]


def test_the_keys_a_chief_flow_sends_pass_the_gate(client, project, started):
    chief = _chief("operator", project)
    run = {
        "kind": "single",
        "board": "feature",
        "scope": "demo",
        "adapter": "claude",
        "model": "claude-sonnet-4-6",
        "project_root": str(project),
    }

    assert _passed(client.post("/runs", json=run, headers=chief.headers))
    assert _passed(
        client.post(
            "/comms/post",
            json=_msg("note", board="feature", scope="demo", project_root=str(project)),
            headers=chief.headers,
        )
    )
    assert _passed(
        client.get(
            f"/comms?feature=demo&board=feature&limit=5&project_root={project}",
            headers=chief.headers,
        )
    )
