"""Tests for Phase 12 — mode param in /comms/search + hybrid default in retrieval.

POST /comms/search must:
  - Default to 'hybrid' mode when mode param is absent.
  - Return keyword-ranked results for mode='keyword'.
  - Reject invalid modes gracefully (fall back to hybrid).
  - Degrade mode='semantic' to keyword matching when no embedding model is available.
  - Return [] when nothing matches — results are never padded with recent messages.
    (Semantic hits are additionally floored at SEMANTIC_DISTANCE_CEILING; BM25
    keyword hits bypass the floor.)

retrieve_board_context() must now call search_by_hybrid internally.
"""

from __future__ import annotations

import json

import pytest


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


def _post(
    client,
    text: str,
    msg_type: str = "discovery",
    board: str = "feature",
    scope: str = "demo",
) -> str:
    r = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "builder",
            "type": msg_type,
            "text": text,
            "board": board,
            "scope": scope,
        },
    )
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


def _search(
    client,
    query: str,
    mode: str | None = None,
    feature: str = "demo",
    board: str = "feature",
    scope: str = "demo",
    k: int = 5,
) -> list:
    payload: dict = {
        "query": query,
        "feature": feature,
        "board": board,
        "scope": scope,
        "k": k,
    }
    if mode is not None:
        payload["mode"] = mode
    r = client.post("/comms/search", json=payload)
    assert r.status_code == 200, f"search failed: {r.data}"
    return json.loads(r.data)


# ---------------------------------------------------------------------------
# mode='semantic' regression — must behave identically to pre-Phase-12 code
# ---------------------------------------------------------------------------


def test_comms_search_mode_semantic_returns_200(client, monkeypatch):
    """mode='semantic' returns HTTP 200."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    _post(client, "Redis cache strategy")
    results = _search(client, "Redis", mode="semantic")
    assert isinstance(results, list)


def test_comms_search_mode_semantic_with_none_embedding_falls_back_to_keyword(
    client, monkeypatch
):
    """mode='semantic' with embed()=None degrades to keyword search — an honest
    literal match, never recency padding (which made every query "match")."""
    import pathly_orchestrator.db.connection as _conn_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    _conn_mod.get_db()  # ensure init has run so _FTS_AVAILABLE is set
    if not _conn_mod._FTS_AVAILABLE:
        pytest.skip("FTS5 not available — keyword fallback not testable")

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    mid = _post(client, "Auth token expiry fix")
    results = _search(client, "Auth", mode="semantic")
    assert any(
        r["id"] == mid for r in results
    ), "semantic+None embedding should degrade to keyword search and find the literal match"


def test_comms_search_mode_semantic_regression_same_as_default_path(
    client, monkeypatch
):
    """mode='semantic' produces same result as direct search_by_embedding call."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    fake_embedding = [0.0] * 384
    monkeypatch.setattr(_emb_mod, "embed", lambda text: fake_embedding)

    captured: list[list] = []
    original_search = _comms_mod.search_by_embedding

    def _capture(*a, **k):
        result = original_search(*a, **k)
        captured.append(result)
        return result

    monkeypatch.setattr(_comms_mod, "search_by_embedding", _capture)

    _post(client, "SQLite migration strategy")
    _search(client, "SQLite", mode="semantic")

    # search_by_embedding should have been called exactly once for semantic mode
    assert (
        len(captured) == 1
    ), f"mode='semantic' should call search_by_embedding once, called {len(captured)} times"


# ---------------------------------------------------------------------------
# mode='keyword'
# ---------------------------------------------------------------------------


def test_comms_search_mode_keyword_returns_200(client):
    """mode='keyword' returns HTTP 200."""
    _post(client, "setupWebGL crash in renderer")
    results = _search(client, "setupWebGL", mode="keyword")
    assert isinstance(results, list)


def test_comms_search_mode_keyword_finds_exact_term(client):
    """mode='keyword' finds a message whose text contains the query term."""
    import pathly_orchestrator.db.connection as _conn_mod

    _conn_mod.get_db()  # ensure init has run so _FTS_AVAILABLE is set
    if not _conn_mod._FTS_AVAILABLE:
        pytest.skip("FTS5 not available — keyword mode not testable")

    mid = _post(client, "setupWebGL crash in renderer process")
    results = _search(client, "setupWebGL", mode="keyword")
    assert any(
        r["id"] == mid for r in results
    ), "keyword mode should return the matching message"


# ---------------------------------------------------------------------------
# mode='hybrid' (default)
# ---------------------------------------------------------------------------


def test_comms_search_mode_hybrid_is_default(client, monkeypatch):
    """When mode is absent, hybrid is the default (search_by_hybrid is called)."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    hybrid_calls: list = []
    original_hybrid = _comms_mod.search_by_hybrid

    def _capture(*a, **k):
        result = original_hybrid(*a, **k)
        hybrid_calls.append(True)
        return result

    monkeypatch.setattr(_comms_mod, "search_by_hybrid", _capture)

    _post(client, "cache invalidation strategy")
    _search(client, "cache", mode=None)  # no mode field — should default to hybrid

    assert len(hybrid_calls) == 1, "Default mode should call search_by_hybrid"


def test_comms_search_mode_hybrid_explicit(client, monkeypatch):
    """Explicit mode='hybrid' calls search_by_hybrid."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    hybrid_calls: list = []
    original_hybrid = _comms_mod.search_by_hybrid

    def _capture(*a, **k):
        result = original_hybrid(*a, **k)
        hybrid_calls.append(True)
        return result

    monkeypatch.setattr(_comms_mod, "search_by_hybrid", _capture)

    _post(client, "deployment pipeline")
    _search(client, "deployment", mode="hybrid")

    assert len(hybrid_calls) == 1, "mode='hybrid' should call search_by_hybrid"


# ---------------------------------------------------------------------------
# Invalid mode falls back to hybrid
# ---------------------------------------------------------------------------


def test_comms_search_mode_invalid_falls_back_to_hybrid(client, monkeypatch):
    """An invalid mode value falls back to hybrid without error."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    hybrid_calls: list = []
    original_hybrid = _comms_mod.search_by_hybrid

    def _capture(*a, **k):
        result = original_hybrid(*a, **k)
        hybrid_calls.append(True)
        return result

    monkeypatch.setattr(_comms_mod, "search_by_hybrid", _capture)

    _post(client, "any message")
    r = client.post(
        "/comms/search",
        json={
            "query": "any",
            "feature": "demo",
            "mode": "invalid_mode_value",
        },
    )
    assert r.status_code == 200
    assert len(hybrid_calls) == 1, "Invalid mode should fall back to hybrid"


# ---------------------------------------------------------------------------
# Honest empties + distance floor
# ---------------------------------------------------------------------------


def test_comms_search_hybrid_no_results_returns_empty(client, monkeypatch):
    """A query matching nothing returns [] — a search result must be a match,
    not merely the newest row on the board (the old recency-padding fallback)."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)
    monkeypatch.setattr(_comms_mod, "search_by_hybrid", lambda *a, **k: [])

    _post(client, "some unrelated board message")
    results = _search(client, "zzznonsense123")
    assert results == []


def test_comms_search_hybrid_keyword_hits_bypass_distance_floor(client, monkeypatch):
    """BM25 keyword hits survive even when the semantic arm floors everything —
    a literal token match is valid regardless of embedding distance."""
    import pathly_orchestrator.db.queries.comms_embeddings as _emb_q
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: [0.0] * 384)
    monkeypatch.setattr(
        _emb_q,
        "search_by_keyword",
        lambda *a, **k: [{"id": "kw1", "text": "literal hit"}],
    )
    monkeypatch.setattr(_emb_q, "search_by_embedding", lambda *a, **k: [])

    results = _search(client, "literal")
    assert [r["id"] for r in results] == ["kw1"]


# ---------------------------------------------------------------------------
# retrieve_board_context uses search_by_hybrid internally
# ---------------------------------------------------------------------------


def test_comms_search_mode_retrieve_board_context_calls_hybrid(client, monkeypatch):
    """retrieve_board_context() delegates to search_by_hybrid for context retrieval."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    hybrid_calls: list = []
    original_hybrid = _comms_mod.search_by_hybrid

    def _capture(*a, **k):
        result = original_hybrid(*a, **k)
        hybrid_calls.append(True)
        return result

    monkeypatch.setattr(_comms_mod, "search_by_hybrid", _capture)

    _post(client, "cache strategy discovery")

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="work on cache",
        board_scope={"feature": True, "project": False, "global": False},
    )

    assert (
        len(hybrid_calls) >= 1
    ), "retrieve_board_context should call search_by_hybrid at least once"


def test_comms_search_mode_retrieve_board_context_returns_block(client, monkeypatch):
    """retrieve_board_context still returns a valid block after switching to hybrid."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    _post(client, "Auth bug: session tokens expire too fast")

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="fix auth",
        board_scope={"feature": True, "project": False, "global": False},
    )

    assert isinstance(block, str)
