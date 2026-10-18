"""chief-agent 03: ``POST /comms/edit`` stamps the edited row with the editor, not the author.

``update_message_text`` used to change ``text`` only, so a row posted with a reviewer's token
kept ``author_source="token"`` / ``author_role="reviewer"`` whoever edited it, and anyone could
put words under that stamp. Now the edit sets the three author columns in the same ``UPDATE``
as the text, from the editor's own run token (or ``none`` when there is none), never from the
request body.
"""

from __future__ import annotations

import pytest

RUN_TOKEN_HEADER = "X-Pathly-Run-Token"
FEATURE = "feat-edit"


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting never spawns background threads during tests."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _mint(run_id: str, role: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    return mint_run_token(get_db(), run_id, role, FEATURE, "/proj", "feature", FEATURE)


def _post(client, token: str | None, text: str = "the reviewer's words") -> str:
    body = {
        "feature": FEATURE,
        "board": "feature",
        "scope": FEATURE,
        "from": "reviewer",
        "type": "discovery",
        "text": text,
    }
    headers = {RUN_TOKEN_HEADER: token} if token else {}
    resp = client.post("/comms/post", json=body, headers=headers)
    assert resp.status_code == 200, resp.data
    return resp.get_json()["message_id"]


def _edit(client, message_id: str, token: str | None, text: str, **extra):
    headers = {RUN_TOKEN_HEADER: token} if token else {}
    return client.post(
        "/comms/edit",
        json={"message_id": message_id, "text": text, **extra},
        headers=headers,
    )


def _row(message_id: str) -> dict:
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute(
            "SELECT text, from_agent, author_role, author_run_id, author_source"
            " FROM comms_messages WHERE id=?",
            (message_id,),
        )
        .fetchone()
    )
    return dict(row)


def test_a_reviewers_row_edited_with_no_token_is_stamped_none(client):
    reviewer = _mint("run-reviewer", "reviewer")
    message_id = _post(client, reviewer)
    posted = _row(message_id)
    assert (posted["author_role"], posted["author_source"]) == ("reviewer", "token")

    resp = _edit(client, message_id, None, "words nobody vouches for")

    assert resp.status_code == 200, resp.data
    row = _row(message_id)
    assert row["text"] == "words nobody vouches for"
    assert row["author_source"] == "none"
    assert row["author_role"] is None
    assert row["author_run_id"] is None


def test_a_reviewers_row_edited_with_a_builder_token_is_stamped_builder(client):
    reviewer = _mint("run-reviewer", "reviewer")
    builder = _mint("run-builder", "builder")
    message_id = _post(client, reviewer)

    resp = _edit(client, message_id, builder, "the builder's rewrite")

    assert resp.status_code == 200, resp.data
    row = _row(message_id)
    assert row["text"] == "the builder's rewrite"
    assert row["author_role"] == "builder"
    assert row["author_source"] == "token"
    assert row["author_run_id"] == "run-builder"


def test_the_body_cannot_name_the_editor(client):
    reviewer = _mint("run-reviewer", "reviewer")
    message_id = _post(client, reviewer)

    resp = _edit(
        client,
        message_id,
        None,
        "claims to be the reviewer",
        **{"from": "reviewer", "run_id": "run-reviewer", "author_role": "reviewer"},
    )

    assert resp.status_code == 200, resp.data
    row = _row(message_id)
    assert row["author_source"] == "none"
    assert row["author_role"] is None
    assert row["author_run_id"] is None


def test_a_revoked_token_edits_as_none(client):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import revoke_run_tokens

    builder = _mint("run-builder", "builder")
    message_id = _post(client, builder)
    revoke_run_tokens(get_db(), "run-builder")

    resp = _edit(client, message_id, builder, "after the run ended")

    assert resp.status_code == 200, resp.data
    row = _row(message_id)
    assert row["text"] == "after the run ended"
    assert row["author_source"] == "none"
    assert row["author_run_id"] is None


@pytest.mark.parametrize("with_token", [False, True])
def test_an_unknown_id_is_still_404(client, with_token):
    token = _mint("run-builder", "builder") if with_token else None

    resp = _edit(client, "no-such-message", token, "anything")

    assert resp.status_code == 404
    assert resp.get_json() == {"ok": False, "error": "Message not found"}


def test_an_unknown_author_source_is_refused_and_writes_nothing(client):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import update_message_text

    reviewer = _mint("run-reviewer", "reviewer")
    message_id = _post(client, reviewer)
    before = _row(message_id)

    with pytest.raises(ValueError, match="author_source"):
        update_message_text(
            get_db(),
            message_id,
            "forged",
            author_role="reviewer",
            author_source="bogus",
        )

    assert _row(message_id) == before
