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


def test_comms_search_hybrid_tags_match_source(client, monkeypatch):
    """Each hybrid row is tagged _match_source (keyword|semantic) so the client can
    group by the arm that matched, plus _distance for ordering semantic hits."""
    import pathly_orchestrator.db.queries.comms_embeddings as _emb_q
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: [0.0] * 384)
    monkeypatch.setattr(
        _emb_q, "search_by_keyword", lambda *a, **k: [{"id": "kw1", "text": "literal"}]
    )
    monkeypatch.setattr(
        _emb_q,
        "search_by_embedding",
        lambda *a, **k: [{"id": "se1", "text": "similar", "_distance": 0.41}],
    )

    by_id = {r["id"]: r for r in _search(client, "literal")}
    assert by_id["kw1"]["_match_source"] == "keyword"
    assert by_id["se1"]["_match_source"] == "semantic"
    assert by_id["se1"]["_distance"] == 0.41


# ---------------------------------------------------------------------------
# FTS query safety — operators are matched literally, never reparsed
# ---------------------------------------------------------------------------


def _fts_ready():
    import pathly_orchestrator.db.connection as _conn_mod

    _conn_mod.get_db()
    return _conn_mod._FTS_AVAILABLE


def test_comms_search_colon_query_is_literal_not_column_filter(client):
    """'code:query' used to be parsed as an FTS5 column filter -> 0 hits. It must
    now match a message whose text literally contains those adjacent terms."""
    if not _fts_ready():
        pytest.skip("FTS5 not available")
    mid = _post(client, "POST /code/query gateway route deliverable")
    results = _search(client, "code:query", mode="keyword")
    assert any(r["id"] == mid for r in results)


def test_comms_search_operator_chars_never_500(client):
    """Raw FTS operators/punctuation must never surface as an error — the query is
    quoted before MATCH, and an all-punctuation query yields [] (guarded)."""
    if not _fts_ready():
        pytest.skip("FTS5 not available")
    for q in ['"', "-", "(", ":", "a OR b", "NEAR(x y)", 'unbalanced "', "-foo"]:
        r = client.post(
            "/comms/search", json={"query": q, "feature": "demo", "mode": "keyword"}
        )
        assert r.status_code == 200, f"query {q!r} -> HTTP {r.status_code}: {r.data}"
        assert isinstance(json.loads(r.data), list)


# ---------------------------------------------------------------------------
# Route hardening + embedder robustness
# ---------------------------------------------------------------------------


def test_comms_search_malformed_body_is_400_not_500(client):
    """A malformed JSON body must be a clean 400 — not a 500 echoing exception text."""
    r = client.post(
        "/comms/search", data="not json at all", content_type="application/json"
    )
    assert r.status_code == 400
    assert "malformed" in json.loads(r.data)["error"].lower()


def test_comms_search_keyword_mode_skips_embedding(client, monkeypatch):
    """Keyword mode must not run the model forward-pass — only hybrid/semantic need it."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    calls: list = []
    monkeypatch.setattr(_emb_mod, "embed", lambda t: calls.append(t) or None)
    _post(client, "cache things here")
    _search(client, "cache", mode="keyword")
    assert calls == [], "keyword mode must not call embed()"


def test_comms_search_long_query_capped_before_embed(client, monkeypatch):
    """A multi-KB query is truncated before it reaches the (lock-held) embedder."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    seen: list = []
    monkeypatch.setattr(_emb_mod, "embed", lambda t: seen.append(len(t)) or None)
    r = client.post(
        "/comms/search", json={"query": "x" * 5000, "feature": "demo", "mode": "hybrid"}
    )
    assert r.status_code == 200
    assert seen and seen[0] <= 512, f"query embedded at length {seen}"


def test_comms_search_k_bounded_and_rejects_bool(client, monkeypatch):
    """k is clamped to [1, 50] and bool (an int subclass) is rejected, not read as 1."""
    import pathly_orchestrator.db.queries.comms as _comms_mod
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda t: None)
    seen: list = []
    monkeypatch.setattr(
        _comms_mod, "search_by_hybrid", lambda *a, **k2: seen.append(a[5]) or []
    )
    for payload_k, expect in [(True, 5), (100000, 50), (0, 5), (7, 7)]:
        seen.clear()
        client.post("/comms/search", json={"query": "q", "feature": "demo", "k": payload_k})
        assert seen == [expect], f"k={payload_k!r} -> {seen}, expected {expect}"


def test_hybrid_reattaches_matched_chunk_on_dual_hit(monkeypatch):
    """A row matched by BOTH arms keeps the semantic child-chunk (the bm25 row, which
    wins the RRF merge, has none) so the 'matched on' line survives the overlap."""
    import pathly_orchestrator.db.queries.comms_embeddings as _emb_q

    monkeypatch.setattr(
        _emb_q, "search_by_keyword", lambda *a, **k: [{"id": "m1", "text": "t"}]
    )
    monkeypatch.setattr(
        _emb_q,
        "search_by_embedding",
        lambda *a, **k: [{"id": "m1", "text": "t", "_distance": 0.4, "_matched_chunk": "the chunk"}],
    )
    out = _emb_q.search_by_hybrid(None, "q", [0.0] * 384, ["feature"], ["demo"], 5)
    assert len(out) == 1
    assert out[0]["_matched_chunk"] == "the chunk"
    assert out[0]["_match_source"] == "keyword"  # in both arms → keyword wins
    assert out[0]["_distance"] == 0.4


def test_embedder_transient_failure_retries_not_permanent_latch(monkeypatch):
    """A transient model-load failure must NOT permanently disable semantic search —
    it retries (up to the cap) and reports its state via embedder_status()."""
    import sys
    import types
    import pathly_orchestrator.runner.embeddings as e

    monkeypatch.setattr(e, "_model", None)
    monkeypatch.setattr(e, "_model_unavailable", False)
    monkeypatch.setattr(e, "_model_load_attempts", 0)

    st = e.embedder_status()
    assert set(st) == {"loaded", "unavailable", "load_attempts"}
    assert st["loaded"] is False and st["unavailable"] is False

    fake = types.ModuleType("sentence_transformers")

    def _boom(_name):
        raise RuntimeError("transient download blip")

    fake.SentenceTransformer = _boom  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake)

    e._load_model()
    assert e._model is None
    assert e._model_load_attempts == 1
    assert e._model_unavailable is False, "transient failure must not hard-latch"
    e._load_model()
    assert e._model_load_attempts == 2, "must retry a transient failure, not give up"


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
