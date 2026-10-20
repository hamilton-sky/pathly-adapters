"""chief-agent 08: HEAD, redirects, lookalike paths and methods no route has.

A request that runs no view is not the gate's to refuse; a redirect's target is.
"""

from __future__ import annotations

import pytest

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
    project,
)

# --- HEAD, redirects and paths no route matches -------------------------------------------


def test_head_is_read_as_get(client, project):
    chief = _chief("status", project)

    assert client.head("/comms?feature=demo", headers=chief.headers).status_code == 200
    for path in ("/events/spawn", "/events/runner?topic=x", "/db/settings"):
        assert client.head(path, headers=chief.headers).status_code == 403, path


def test_a_post_only_route_has_no_head(client, project):
    chief = _chief("operator", project)

    assert client.head("/db/query", headers=chief.headers).status_code == 405


REDIRECTED = [
    ("post", "/db//query", {"sql": "SELECT 1 AS n"}),
    ("post", "/comms//post", _msg("note")),
    ("get", "/events//spawn", None),
    ("get", "/db//settings", None),
]


@pytest.mark.parametrize(
    "verb,path,body", REDIRECTED, ids=[f"{v} {p}" for v, p, _ in REDIRECTED]
)
def test_a_redirect_runs_no_view_and_its_target_is_gated(
    client, project, verb, path, body
):
    chief = _chief("operator", project)
    kwargs = {"json": body} if body is not None else {}

    first = getattr(client, verb)(path, headers=chief.headers, **kwargs)
    assert first.status_code == 308, (first.status_code, first.get_data(as_text=True))

    followed = getattr(client, verb)(
        path, headers=chief.headers, follow_redirects=True, **kwargs
    )
    if path.startswith("/comms"):
        assert followed.status_code == 200
    else:
        assert _gated(followed), (followed.status_code, followed.get_data(as_text=True))
    assert _count("SELECT COUNT(*) FROM comms_messages WHERE type = 'note'") == (
        1 if path.startswith("/comms") else 0
    )


NOT_RUN_PATHS = [
    "/DB/query",
    "/db/query/",
    "/db/./query",
    "//db/query",
    "/comms/../db/query",
    "/db/query;x=1",
    "/db/query%00",
    "/db/query%2F",
]


@pytest.mark.parametrize("path", NOT_RUN_PATHS)
def test_a_lookalike_path_never_reaches_an_unlisted_view(client, project, path):
    chief = _chief("operator", project)

    resp = client.post(path, json={"sql": "SELECT 1 AS n"}, headers=chief.headers)

    assert _gated(resp) or resp.status_code in (308, 404, 405), (
        resp.status_code,
        resp.get_data(as_text=True)[:200],
    )


@pytest.mark.parametrize("method", ["put", "delete", "patch"])
@pytest.mark.parametrize("path", ["/db/query", "/events/spawn", "/comms/delete"])
def test_a_method_no_route_has_is_a_405(client, project, method, path):
    chief = _chief("operator", project)

    resp = getattr(client, method)(path, headers=chief.headers)

    assert resp.status_code == 405
