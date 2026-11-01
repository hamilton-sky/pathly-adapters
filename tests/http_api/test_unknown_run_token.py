"""chief-autopilot 10: a run token Pathly does not know is refused, not treated as anonymous.

``run_token_guard`` is a ``before_request`` hook registered before the chief gate. A request
whose ``X-Pathly-Run-Token`` does not resolve to a live token (never minted, or revoked) gets 401
``{"error": "unknown run token"}`` on every route, because anonymous loopback callers may do
everything and a leaked or invented token must not be a way around the chief gate. A request
with no header, or with the header empty, is anonymous as before, and a live token of any role
passes on to the chief gate and the route.
"""

from __future__ import annotations

import pytest

from chief_gate_support import (
    _chief,
    _msg,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    project,
)

UNKNOWN = {"error": "unknown run token"}


def _calls(client, headers: dict) -> list:
    """A GET, a board post and the chief hook's route, each sent with ``headers``."""
    return [
        client.get("/db/settings", headers=headers),
        client.post(
            "/comms/post", json=_msg("note", **{"from": "builder"}), headers=headers
        ),
        client.post(
            "/chief/human-messages",
            json={"run_id": "chief-x", "text": "hi", "hook_secret": "s"},
            headers=headers,
        ),
    ]


def _builder_token(project, run_id: str = "run-b") -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    return mint_run_token(
        get_db(), run_id, "builder", "demo", str(project), "feature", "demo"
    )


@pytest.mark.parametrize("token", ["nope", "x" * 43])
def test_an_invented_token_is_401_on_every_kind_of_route(client, token):
    for resp in _calls(client, {"X-Pathly-Run-Token": token}):
        assert resp.status_code == 401, resp.request.path
        assert resp.get_json() == UNKNOWN, resp.request.path


def test_a_revoked_builder_token_is_401_on_every_kind_of_route(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import revoke_run_tokens

    token = _builder_token(project, "run-r")
    revoke_run_tokens(get_db(), "run-r")

    for resp in _calls(client, {"X-Pathly-Run-Token": token}):
        assert resp.status_code == 401, resp.request.path
        assert resp.get_json() == UNKNOWN, resp.request.path


def test_a_refused_token_writes_nothing(client):
    from pathly_orchestrator.db.connection import get_db

    before = get_db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]
    resp = client.post(
        "/comms/post",
        json=_msg("note", **{"from": "builder"}),
        headers={"X-Pathly-Run-Token": "nope"},
    )

    assert resp.status_code == 401
    after = get_db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]
    assert after == before


@pytest.mark.parametrize("headers", [{}, {"X-Pathly-Run-Token": ""}])
def test_no_header_and_an_empty_header_are_anonymous_as_before(client, headers):
    settings, post, human = _calls(client, headers)

    assert settings.status_code == 200
    assert post.status_code == 200
    assert human.status_code == 404
    assert human.get_json() == {"error": "no open chief session"}


def test_a_live_builder_token_is_unchanged(client, project):
    headers = {"X-Pathly-Run-Token": _builder_token(project)}

    settings, post, human = _calls(client, headers)

    assert settings.status_code == 200
    assert post.status_code == 200
    assert human.status_code == 404


def test_a_live_chief_token_is_unchanged(client, project):
    chief = _chief("operator", project)

    resp = client.get("/comms?feature=demo", headers=chief.headers)
    assert resp.status_code == 200

    refused = client.post(
        "/chief/human-messages",
        json={"run_id": chief.run_id, "text": "hi", "hook_secret": "s"},
        headers=chief.headers,
    )
    assert refused.status_code == 403
    assert "allowed" in refused.get_json()


def test_a_chief_whose_token_was_revoked_at_close_gets_401(client, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import revoke_run_tokens

    chief = _chief("operator", project)
    conn = get_db()
    revoke_run_tokens(conn, chief.run_id)
    conn.execute(
        "UPDATE chief_sessions SET closed_at = 1.0 WHERE run_id = ?", (chief.run_id,)
    )
    conn.commit()

    for resp in [
        client.get("/comms?feature=demo", headers=chief.headers),
        *_calls(client, chief.headers),
    ]:
        assert resp.status_code == 401, resp.request.path


def test_the_audit_does_not_read_a_pipe_as_a_file_in_the_cwd():
    """``chief_audit_support`` names the file an audited descriptor is open on. A pipe has none:
    Linux's readlink says ``pipe:[N]``, which must not be joined to the working directory (torch's
    first import runs ``ldconfig`` through one during an audited request)."""
    import os

    from chief_audit_support import _absolute, _fd_path

    read_end, write_end = os.pipe()
    try:
        assert _fd_path(read_end) is None
        assert _absolute(read_end) is None
    finally:
        os.close(read_end)
        os.close(write_end)
