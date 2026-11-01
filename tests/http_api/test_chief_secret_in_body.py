"""chief-autopilot 02: a chief-token body holding the chief's own hook secret is refused.

Defence in depth beside the deny rules (``test_chief_secret_reach.py``): a body any of whose
string values holds the session's hook secret, alone or inside a longer token-like run, gets 400
``{"error": "the body contains this chief's hook secret"}`` and nothing is stored. The scan is
``db/secret_scan.contains_secret_hash`` against ``chief_sessions.hook_secret_hash``. An ordinary
body, one with ``<`` in it, and a builder token's body holding the same text are unaffected.
"""

from __future__ import annotations

import hashlib
import secrets

import pytest

from chief_gate_support import (
    _chief,
    _count,
    _msg,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    project,
)

REFUSED = {"error": "the body contains this chief's hook secret"}
POSTS = "SELECT COUNT(*) FROM comms_messages"


@pytest.fixture()
def secret() -> str:
    return secrets.token_urlsafe(32)


@pytest.fixture()
def chief(project, secret):
    from pathly_orchestrator.db.connection import get_db

    made = _chief("operator", project)
    conn = get_db()
    conn.execute(
        "UPDATE chief_sessions SET hook_secret_hash=? WHERE run_id=?",
        (hashlib.sha256(secret.encode()).hexdigest(), made.run_id),
    )
    conn.commit()
    return made


def _post(client, headers, text: str, **extra):
    return client.post(
        "/comms/post", json=_msg("note", text=text, **extra), headers=headers
    )


def _directive(client, headers, project, text: str):
    body = {"project_root": str(project), "to_agent": "*", "text": text}
    return client.post("/comms/directives", json=body, headers=headers)


def _hidden(secret: str) -> list[str]:
    """The secret alone, inside a longer URL-safe run, and inside prose."""
    return [secret, f"x{secret}", f"ab-{secret}_cd", f"the secret is {secret}."]


def test_a_post_whose_text_holds_the_secret_is_400_and_stores_nothing(
    client, chief, secret
):
    before = _count(POSTS)
    for text in _hidden(secret):
        resp = _post(client, chief.headers, text)
        assert resp.status_code == 400, text
        assert resp.get_json() == REFUSED, text
    assert _count(POSTS) == before


@pytest.mark.parametrize(
    "where",
    [
        lambda secret: {"summary": f"x{secret}"},
        lambda secret: {"type": "question", "options": ["a", f"x{secret}"]},
    ],
    ids=["summary", "options-list"],
)
def test_a_post_whose_other_field_holds_the_secret_is_400(client, chief, secret, where):
    before = _count(POSTS)
    resp = _post(client, chief.headers, "hello", **where(secret))
    assert resp.status_code == 400, resp.get_json()
    assert resp.get_json() == REFUSED
    assert _count(POSTS) == before


@pytest.mark.parametrize(
    "where",
    [
        lambda: {"summary": "a short summary"},
        lambda: {"type": "question", "options": ["a", "b"]},
    ],
    ids=["summary", "options-list"],
)
def test_the_same_fields_without_the_secret_pass(client, chief, where):
    resp = _post(client, chief.headers, "hello", **where())
    assert resp.status_code in (200, 201), resp.get_json()


def test_a_directive_whose_text_holds_the_secret_is_400_and_stores_nothing(
    client, chief, secret, project
):
    before = _count(POSTS)
    for text in _hidden(secret):
        resp = _directive(client, chief.headers, project, text)
        assert resp.status_code == 400, text
        assert resp.get_json() == REFUSED, text
    assert _count(POSTS) == before


@pytest.mark.parametrize("text", ["hello", "a < b and c > d", "x<y", "<<EOF"])
def test_an_ordinary_post_is_unaffected(client, chief, text):
    before = _count(POSTS)
    resp = _post(client, chief.headers, text)
    assert resp.status_code in (200, 201), resp.get_json()
    assert _count(POSTS) == before + 1


@pytest.mark.parametrize("text", ["Run the formatter.", "Keep a < b in mind."])
def test_an_ordinary_directive_is_unaffected(client, chief, project, text):
    resp = _directive(client, chief.headers, project, text)
    assert resp.status_code == 201, resp.get_json()


def test_another_secret_is_not_this_chiefs(client, chief):
    resp = _post(client, chief.headers, secrets.token_urlsafe(32))
    assert resp.status_code in (200, 201), resp.get_json()


def test_a_builder_token_is_unaffected(client, chief, secret, project):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    token = mint_run_token(
        get_db(), "run-b", "builder", "demo", str(project), "feature", "demo"
    )
    before = _count(POSTS)
    resp = _post(client, {"X-Pathly-Run-Token": token}, secret, **{"from": "builder"})
    assert resp.status_code in (200, 201), resp.get_json()
    assert _count(POSTS) == before + 1
