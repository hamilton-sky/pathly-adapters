"""caller_identity(request): the caller is the holder of a live run token, never a body field."""

from __future__ import annotations

import logging

import pytest


@pytest.fixture()
def app():
    from pathly_orchestrator.http_server import app as flask_app

    flask_app.config["TESTING"] = True
    return flask_app


def _identity(app, headers=None, json_body=None, remote="10.1.2.3"):
    from pathly_orchestrator.http_server.run_identity import caller_identity

    with app.test_request_context(
        "/comms",
        method="POST",
        headers=headers or {},
        json=json_body,
        environ_base={"REMOTE_ADDR": remote},
    ):
        from flask import request

        return caller_identity(request)


def _mint(run_id="run-1", role="builder"):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    conn = get_db()
    return mint_run_token(conn, run_id, role, "feat-a", "/proj", "feature", "feat-a")


def test_valid_token_resolves_to_run(app):
    token = _mint()
    ident = _identity(app, {"X-Pathly-Run-Token": token})
    assert ident.kind == "run"
    assert ident.run_id == "run-1"
    assert ident.role == "builder"
    assert ident.feature == "feat-a"
    assert ident.project_root == "/proj"
    assert ident.board == "feature"
    assert ident.scope == "feat-a"


@pytest.mark.parametrize("headers", [{}, {"X-Pathly-Run-Token": ""}])
def test_missing_or_empty_is_anonymous(app, headers):
    ident = _identity(app, headers)
    assert ident.kind == "anonymous"
    assert (ident.run_id, ident.role, ident.feature) == (None, None, None)
    assert (ident.project_root, ident.board, ident.scope) == (None, None, None)


def test_unknown_token_is_anonymous_and_logged(app, caplog):
    with caplog.at_level(logging.INFO):
        ident = _identity(app, {"X-Pathly-Run-Token": "nope"}, remote="10.9.8.7")
    assert ident.kind == "anonymous"
    assert ident.role is None
    lines = [r for r in caplog.records if "10.9.8.7" in r.getMessage()]
    assert len(lines) == 1
    assert lines[0].levelno == logging.INFO


def test_revoked_token_is_anonymous_and_logged(app, caplog):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import revoke_run_tokens

    token = _mint("run-2")
    revoke_run_tokens(get_db(), "run-2")
    with caplog.at_level(logging.INFO):
        ident = _identity(app, {"X-Pathly-Run-Token": token}, remote="10.9.8.6")
    assert ident.kind == "anonymous"
    assert ident.run_id is None
    assert len([r for r in caplog.records if "10.9.8.6" in r.getMessage()]) == 1


def test_missing_token_is_not_logged(app, caplog):
    with caplog.at_level(logging.INFO):
        _identity(app, {}, remote="10.9.8.5")
    assert not [r for r in caplog.records if "10.9.8.5" in r.getMessage()]


def test_body_role_human_without_token_is_anonymous(app):
    ident = _identity(app, json_body={"role": "human", "run_id": "x", "from": "human"})
    assert ident.kind == "anonymous"
    assert ident.role is None
    assert ident.run_id is None


def test_body_fields_do_not_override_token(app):
    token = _mint("run-3", "reviewer")
    ident = _identity(
        app,
        {"X-Pathly-Run-Token": token},
        {"role": "human", "run_id": "other", "from": "human"},
    )
    assert (ident.kind, ident.role, ident.run_id) == ("run", "reviewer", "run-3")


def test_cors_preflight_allows_run_token_header(app):
    with app.test_client() as c:
        resp = c.options("/comms", headers={"Origin": "http://localhost"})
    allowed = resp.headers.get("Access-Control-Allow-Headers", "")
    assert "X-Pathly-Run-Token" in allowed


def test_cors_response_headers_allow_run_token_header(app):
    with app.test_client() as c:
        resp = c.get("/comms/goals?feature=x")
    assert "X-Pathly-Run-Token" in resp.headers.get("Access-Control-Allow-Headers", "")
