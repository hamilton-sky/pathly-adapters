"""role-read-policy: the caller's identity comes from X-Pathly-Run-Token only."""

from __future__ import annotations

import pytest
from flask import Flask

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_tokens import mint_run_token, revoke_run_tokens


@pytest.fixture()
def app():
    return Flask(__name__)


def _ident(app, headers=None, json=None):
    from pathly_orchestrator.http_server.run_identity import caller_identity

    with app.test_request_context(
        "/x", method="POST", headers=headers or {}, json=json
    ):
        return caller_identity(__import__("flask").request)


def _mint(run_id="run-1"):
    return mint_run_token(
        get_db(), run_id, "builder", "feat", "/proj", "feat", "feature"
    )


def test_valid_token_is_run(app) -> None:
    ident = _ident(app, {"X-Pathly-Run-Token": _mint()})
    assert ident.kind == "run"
    assert ident.run_id == "run-1"
    assert ident.role == "builder"
    assert ident.feature == "feat"
    assert ident.project_root == "/proj"
    assert ident.board == "feat"
    assert ident.scope == "feature"


@pytest.mark.parametrize(
    "headers", [{}, {"X-Pathly-Run-Token": ""}, {"X-Pathly-Run-Token": "nope"}]
)
def test_missing_empty_unknown_are_anonymous(app, headers) -> None:
    ident = _ident(app, headers)
    assert ident.kind == "anonymous"
    assert ident.run_id is None and ident.role is None


def test_revoked_is_anonymous(app) -> None:
    tok = _mint("run-9")
    revoke_run_tokens(get_db(), "run-9")
    assert _ident(app, {"X-Pathly-Run-Token": tok}).kind == "anonymous"


def test_body_role_without_token_is_anonymous(app) -> None:
    ident = _ident(app, json={"role": "human", "run_id": "run-1", "from": "human"})
    assert ident.kind == "anonymous"
    assert ident.role is None


def test_body_role_does_not_override_token(app) -> None:
    ident = _ident(app, {"X-Pathly-Run-Token": _mint()}, json={"role": "human"})
    assert ident.role == "builder"


def test_cors_preflight_allows_token_header() -> None:
    from pathly_orchestrator.http_server import app as real_app

    with real_app.test_client() as c:
        r = c.options("/comms/post")
    assert "X-Pathly-Run-Token" in r.headers["Access-Control-Allow-Headers"]
