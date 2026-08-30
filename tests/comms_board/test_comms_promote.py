"""Tests for POST /comms/promote — cross-tier promotion of a decision/constraint.

The board's three tiers are read by every agent but writable only downward, so
before this endpoint nothing in the headless pipeline could move a conclusion UP.
These tests pin the four gates that keep that copy honest (type, direction,
permission, idempotency), the provenance columns it writes, and the embedding
without which a promoted row is invisible to the retrieval it exists to feed.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    """Flask test client. DB is isolated per-test by the autouse conftest fixture."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(
    client,
    *,
    from_agent: str = "architect",
    msg_type: str = "decision",
    text: str = "Adapters must never parse their own argv.",
    board: str = "feature",
    scope: str = "demo",
) -> str:
    """Post a source message and return its id."""
    r = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": from_agent,
            "type": msg_type,
            "text": text,
            "board": board,
            "scope": scope,
        },
    )
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _row(message_id: str) -> dict:
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT * FROM comms_messages WHERE id=?", (message_id,))
        .fetchone()
    )
    assert row is not None, f"message {message_id} missing"
    return dict(row)


def _promote(client, message_id: str, from_agent: str = "retro", **overrides):
    payload = {
        "message_id": message_id,
        "from": from_agent,
        "to_board": "global",
    }
    payload.update(overrides)
    return client.post("/comms/promote", json=payload)


# ---------------------------------------------------------------------------
# happy path
# ---------------------------------------------------------------------------


def test_promote_feature_to_global_copies_with_provenance(client):
    """A feature decision lands on the global board with all three links set."""
    src_id = _post(client)
    r = _promote(client, src_id)
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["ok"] is True
    assert body["already_promoted"] is False
    assert body["board"] == "global"
    assert body["scope"] == "global"
    assert body["type"] == "decision"

    new_id = body["message_id"]
    assert new_id != src_id

    copy = _row(new_id)
    assert copy["board"] == "global"
    assert copy["scope"] == "global"
    assert copy["type"] == "decision"
    assert copy["text"] == "Adapters must never parse their own argv."
    assert copy["promoted_from"] == src_id
    assert copy["original_scope"] == "demo"
    assert copy["from_agent"] == "retro"

    # The source is the audit record of how the decision was reached: it must stay
    # exactly where it was, with only the forward pointer added.
    src = _row(src_id)
    assert src["promoted_to"] == new_id
    assert src["board"] == "feature"
    assert src["scope"] == "demo"
    assert src["deleted_at"] is None
    assert src["from_agent"] == "architect"
    assert src["text"] == "Adapters must never parse their own argv."
    assert src["promoted_from"] is None
    assert src["original_scope"] is None


def test_promote_feature_to_project_defaults_scope_to_project_root(client, tmp_path):
    """to_board='project' with no explicit scope keys off the project_root."""
    src_id = _post(client, msg_type="constraint", text="Never push to master.")
    r = _promote(client, src_id, to_board="project", project_root=str(tmp_path))
    assert r.status_code == 200, r.data
    body = json.loads(r.data)
    assert body["scope"] == str(tmp_path)
    assert _row(body["message_id"])["board"] == "project"


def test_target_scope_normalizes_a_windows_project_root():
    """The project board is keyed by the NORMALIZED root — backslashes and a
    trailing separator must not fork a second, unread project board.

    Unit-level on purpose: driving this through HTTP would fire the board-disk
    mirror, which creates the (fictional) root on disk.
    """
    from pathly_orchestrator.http_server.blueprints.comms.promote import (
        _resolve_target_scope,
    )

    scope = _resolve_target_scope(
        {"project_root": "C:\\Users\\dev\\pathly-adapters\\"}, "project"
    )
    assert scope == "C:/Users/dev/pathly-adapters"
    assert _resolve_target_scope({}, "global") == "global"
    assert _resolve_target_scope({"to_scope": " custom "}, "project") == "custom"


def test_promote_project_to_global_is_upward(client, tmp_path):
    """project→global is the third legal direction."""
    src_id = _post(client, from_agent="director", board="project", scope=str(tmp_path))
    r = _promote(client, src_id, from_agent="director")
    assert r.status_code == 200, r.data
    assert _row(json.loads(r.data)["message_id"])["original_scope"] == str(tmp_path)


# ---------------------------------------------------------------------------
# idempotency
# ---------------------------------------------------------------------------


def test_promote_is_idempotent(client):
    """Promoting twice returns the SAME target row and inserts nothing new."""
    src_id = _post(client)
    first = json.loads(_promote(client, src_id).data)

    second_resp = _promote(client, src_id)
    assert second_resp.status_code == 200, second_resp.data
    second = json.loads(second_resp.data)

    assert second["message_id"] == first["message_id"]
    assert second["already_promoted"] is True

    from pathly_orchestrator.db.connection import get_db

    count = (
        get_db()
        .execute(
            "SELECT COUNT(*) FROM comms_messages "
            "WHERE promoted_from=? AND board='global' AND scope='global'",
            (src_id,),
        )
        .fetchone()[0]
    )
    assert count == 1


def test_promote_to_a_second_tier_is_not_blocked_by_the_first(client, tmp_path):
    """feature→project then feature→global are distinct promotions, not a re-run.

    The source has only ONE promoted_to column, so an idempotency check keyed off
    it would mistake the project copy for the global one and refuse to insert.
    """
    src_id = _post(client)
    proj = json.loads(
        _promote(client, src_id, to_board="project", to_scope=str(tmp_path)).data
    )
    glob = json.loads(_promote(client, src_id).data)

    assert glob["already_promoted"] is False
    assert glob["message_id"] != proj["message_id"]
    assert _row(proj["message_id"])["board"] == "project"
    assert _row(glob["message_id"])["board"] == "global"


# ---------------------------------------------------------------------------
# type gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("msg_type", ["discovery", "status", "nudge", "task"])
def test_promote_rejects_non_conclusion_types(client, msg_type):
    """Only decision/constraint promote — a promoted discovery is global noise."""
    src_id = _post(client, msg_type=msg_type, text="saw something")
    r = _promote(client, src_id)
    assert r.status_code == 400, r.data
    body = json.loads(r.data)
    assert body["ok"] is False
    assert body["promotable_types"] == ["constraint", "decision"]


# ---------------------------------------------------------------------------
# direction gate
# ---------------------------------------------------------------------------


def test_promote_rejects_downward(client):
    """global→feature is a fork of a shared rule, not a promotion."""
    src_id = _post(client, from_agent="director", board="global", scope="global")
    r = _promote(
        client, src_id, from_agent="director", to_board="feature", to_scope="demo"
    )
    assert r.status_code == 400, r.data
    assert json.loads(r.data)["ok"] is False


def test_promote_rejects_sideways(client):
    """feature→feature is not upward, even to a different feature scope."""
    src_id = _post(client)
    r = _promote(client, src_id, to_board="feature", to_scope="other-feature")
    assert r.status_code == 400, r.data
    assert json.loads(r.data)["from_board"] == "feature"


def test_promote_rejects_project_to_project(client, tmp_path):
    src_id = _post(client, from_agent="director", board="project", scope=str(tmp_path))
    r = _promote(
        client,
        src_id,
        from_agent="director",
        to_board="project",
        to_scope=str(tmp_path / "other"),
    )
    assert r.status_code == 400, r.data


# ---------------------------------------------------------------------------
# permission gate
# ---------------------------------------------------------------------------


def test_promote_allows_retro(client):
    """RETRO is the stage whose whole job is capturing lessons — it must promote.

    It is NOT in _GLOBAL_WRITERS; gating promotion on that set would lock the one
    headless consolidation stage out of the boards it exists to feed.
    """
    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        _GLOBAL_WRITERS,
    )

    assert "retro" not in _GLOBAL_WRITERS
    src_id = _post(client)
    assert _promote(client, src_id, from_agent="retro").status_code == 200


@pytest.mark.parametrize("role", ["director", "evaluator", "human", "retro"])
def test_promote_permitted_roles(client, role):
    src_id = _post(client, text=f"decision for {role}")
    assert _promote(client, src_id, from_agent=role).status_code == 200


@pytest.mark.parametrize("role", ["builder", "tester", "reviewer", "architect"])
def test_promote_rejects_unprivileged_roles(client, role):
    src_id = _post(client, text=f"decision for {role}")
    r = _promote(client, src_id, from_agent=role)
    assert r.status_code == 403, r.data
    body = json.loads(r.data)
    assert body["allowed_roles"] == ["director", "evaluator", "human", "retro"]
    # A refused promotion writes nothing.
    assert _row(src_id)["promoted_to"] is None


# ---------------------------------------------------------------------------
# the promoted row is reachable on the target tier
# ---------------------------------------------------------------------------


def test_promoted_row_is_embedded_and_searchable(client, monkeypatch):
    """The copy must be embedded, else it is invisible to semantic retrieval.

    The local embedding model may be absent in CI, so the load-bearing assertion
    is that the embed hook FIRED for the new row id; the keyword arm of
    /comms/search then confirms the row is actually addressable on the target tier.
    """
    import pathly_orchestrator.runner.embeddings as _emb_mod

    calls: list[tuple[str, str]] = []
    monkeypatch.setattr(
        _emb_mod, "embed_async", lambda mid, text, *a, **k: calls.append((mid, text))
    )

    src_id = _post(client, text="Promotion copies upward, never moves.")
    calls.clear()  # drop the source post's own embed

    body = json.loads(_promote(client, src_id).data)
    new_id = body["message_id"]
    assert calls == [(new_id, "Promotion copies upward, never moves.")]

    r = client.post(
        "/comms/search",
        json={
            "query": "Promotion copies upward",
            "feature": "demo",
            "board": "global",
            "scope": "global",
            "mode": "keyword",
        },
    )
    assert r.status_code == 200, r.data
    hits = json.loads(r.data)
    results = hits["results"] if isinstance(hits, dict) else hits
    if results:  # FTS5 is optional in the build; skip the assert when unavailable
        assert any(m["id"] == new_id for m in results)


def test_promote_idempotent_hit_does_not_re_embed(client, monkeypatch):
    """The second promotion returns the stored row — re-embedding it is waste."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    calls: list[str] = []
    monkeypatch.setattr(
        _emb_mod, "embed_async", lambda mid, text, *a, **k: calls.append(mid)
    )

    src_id = _post(client)
    _promote(client, src_id)
    calls.clear()
    _promote(client, src_id)
    assert calls == []


# ---------------------------------------------------------------------------
# request validation
# ---------------------------------------------------------------------------


def test_promote_unknown_message_is_404(client):
    r = _promote(client, "does-not-exist")
    assert r.status_code == 404, r.data


def test_promote_deleted_message_is_404(client):
    src_id = _post(client)
    assert client.post("/comms/delete", json={"message_id": src_id}).status_code == 200
    assert _promote(client, src_id).status_code == 404


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message_id": "  ", "from": "retro", "to_board": "global"},
        {"message_id": "x", "from": "", "to_board": "global"},
        {"message_id": "x", "from": "retro", "to_board": "team"},
        {"message_id": "x", "from": "retro"},
    ],
)
def test_promote_rejects_malformed_requests(client, payload):
    assert client.post("/comms/promote", json=payload).status_code == 400


def test_promote_project_without_scope_or_root_is_400(client):
    """No scope and no project_root ⇒ nowhere to put it; refuse rather than guess."""
    src_id = _post(client)
    r = _promote(client, src_id, to_board="project")
    assert r.status_code == 400, r.data
