"""Regression tests for POST /skills/preview — the MD Editor's live preview pane.

The bug these guard: `_inject_prompt_vars` moved from `fsm_ops` to `fsm_compose`
during the SOLID split, but the lazy import in `editor_render.skills_preview` still
read it from `fsm_ops`. Because the import lives INSIDE the route, it only blew up at
request time — every "open an artifact in the editor" preview 500'd while the suite
stayed green. These tests exercise the endpoint end-to-end so that whole class of
stale lazy-import regression is caught.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_preview_body_cells_returns_200(client):
    """Opening an artifact (raw body cells, no registered skill) renders, not 500."""
    r = client.post(
        "/skills/preview",
        json={
            "body_cells": [
                {"type": "body", "content": "# Architecture Proposal\n\nSome **body**."}
            ],
            "feature_path": "",
        },
    )
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    # The live pane consumes the compiled sections; the endpoint must return them.
    assert "sections" in body


def test_preview_injects_prompt_vars(client):
    """A <feature> placeholder is substituted — proves the _inject_prompt_vars hop runs."""
    r = client.post(
        "/skills/preview",
        json={
            "body_cells": [
                {"type": "body", "content": "# Notes for <feature>\n\nbody"}
            ],
            "feature_path": "C:/proj/pathly/plans/my-feature",
        },
    )
    assert r.status_code == 200, r.data
    blob = json.dumps(json.loads(r.data))
    assert "<feature>" not in blob, "placeholder must be substituted by _inject_prompt_vars"
    assert "my-feature" in blob


def test_preview_requires_skill_or_body(client):
    """Empty preview request is a 400, not a 500."""
    r = client.post("/skills/preview", json={})
    assert r.status_code == 400
