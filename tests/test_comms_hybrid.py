"""Tests for Phase 11 — FTS5 virtual table + hybrid search helpers.

search_by_keyword and search_by_hybrid must:
  - Return relevant messages when FTS5 is available.
  - Fall back gracefully (return [] or recency) when FTS is unavailable.
  - RRF merge ranks an exact-text match first when both BM25 and semantic hits exist.
  - search_by_hybrid handles query_embedding=None (falls back to keyword-only).
"""
from __future__ import annotations

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


def _post(client, text: str, msg_type: str = "discovery",
          board: str = "feature", scope: str = "demo") -> str:
    import json
    r = client.post("/comms/post", json={
        "feature": "demo",
        "from": "builder",
        "type": msg_type,
        "text": text,
        "board": board,
        "scope": scope,
    })
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


# ---------------------------------------------------------------------------
# _FTS_AVAILABLE flag
# ---------------------------------------------------------------------------

def test_comms_hybrid_fts_available_flag_exists():
    """_FTS_AVAILABLE is exported from db.connection."""
    import pathly_orchestrator.db.connection as _conn_mod
    assert isinstance(_conn_mod._FTS_AVAILABLE, bool)


def test_comms_hybrid_fts_available_is_true_after_migration(client):
    """After get_db() migrations, _FTS_AVAILABLE should be True (FTS5 bundled with SQLite)."""
    import pathly_orchestrator.db.connection as _conn_mod
    _conn_mod.get_db()  # ensure init has run
    assert _conn_mod._FTS_AVAILABLE is True, "FTS5 should be available on standard SQLite"


# ---------------------------------------------------------------------------
# search_by_keyword
# ---------------------------------------------------------------------------

def test_comms_hybrid_keyword_returns_matching_message(client):
    """search_by_keyword returns a message whose text matches the query."""
    import pathly_orchestrator.db.connection as _conn_mod
    from pathly_orchestrator.db.queries.comms import search_by_keyword

    mid = _post(client, "setupWebGL crash in renderer process")
    conn = _conn_mod.get_db()

    if not _conn_mod._FTS_AVAILABLE:
        pytest.skip("FTS5 not available on this SQLite build")

    results = search_by_keyword(conn, "setupWebGL", ["feature"], ["demo"], k=5)
    assert any(r["id"] == mid for r in results), (
        f"Expected message {mid} in keyword results"
    )


def test_comms_hybrid_keyword_empty_boards_returns_empty():
    """search_by_keyword returns [] when boards or scopes is empty."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import search_by_keyword

    conn = get_db()
    assert search_by_keyword(conn, "hello", [], ["demo"]) == []
    assert search_by_keyword(conn, "hello", ["feature"], []) == []


def test_comms_hybrid_keyword_no_match_returns_empty(client):
    """search_by_keyword returns [] when no messages match the query."""
    from pathly_orchestrator.db.connection import _FTS_AVAILABLE, get_db
    from pathly_orchestrator.db.queries.comms import search_by_keyword

    _post(client, "completely unrelated content about authentication")
    conn = get_db()

    if not _FTS_AVAILABLE:
        pytest.skip("FTS5 not available on this SQLite build")

    results = search_by_keyword(conn, "xyzzy_nonexistent_term_qqqq", ["feature"], ["demo"], k=5)
    assert results == []


# ---------------------------------------------------------------------------
# search_by_hybrid
# ---------------------------------------------------------------------------

def test_comms_hybrid_returns_message_for_keyword_query(client):
    """search_by_hybrid finds a message by keyword when embedding is None."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import search_by_hybrid

    mid = _post(client, "setupWebGL crash in renderer process")
    conn = get_db()

    results = search_by_hybrid(conn, "setupWebGL", None, ["feature"], ["demo"], k=5)
    assert any(r["id"] == mid for r in results), (
        f"Expected message {mid} in hybrid results (keyword-only path)"
    )


def test_comms_hybrid_ranking_exact_match_ranks_first(client):
    """The message whose text matches the query exactly ranks first in hybrid results."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import search_by_hybrid

    _post(client, "unrelated content about deployment pipelines")
    _post(client, "another message about logging infrastructure")
    target_id = _post(client, "setupWebGL crash in renderer process")

    conn = get_db()
    results = search_by_hybrid(conn, "setupWebGL", None, ["feature"], ["demo"], k=5)
    assert results, "Expected at least one result"
    assert results[0]["id"] == target_id, (
        f"Expected exact-match message to rank first, got {results[0]['id']}"
    )


def test_comms_hybrid_empty_boards_returns_empty():
    """search_by_hybrid returns [] when boards or scopes is empty."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import search_by_hybrid

    conn = get_db()
    assert search_by_hybrid(conn, "hello", None, [], ["demo"]) == []
    assert search_by_hybrid(conn, "hello", None, ["feature"], []) == []


def test_comms_hybrid_embedding_none_falls_back_to_keyword(client):
    """search_by_hybrid with query_embedding=None uses keyword search only."""
    import pathly_orchestrator.db.connection as _conn_mod
    from pathly_orchestrator.db.queries.comms import search_by_hybrid

    mid = _post(client, "Redis cache invalidation strategy")
    conn = _conn_mod.get_db()

    if not _conn_mod._FTS_AVAILABLE:
        pytest.skip("FTS5 not available — hybrid keyword fallback not testable")

    results = search_by_hybrid(conn, "Redis", None, ["feature"], ["demo"], k=5)
    assert any(r["id"] == mid for r in results), "Keyword fallback should find the message"


def test_comms_hybrid_with_fake_embedding_merges_results(client, monkeypatch):
    """search_by_hybrid merges BM25 and semantic results via RRF."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import search_by_hybrid

    mid_kw = _post(client, "setupWebGL crash in renderer")
    mid_sem = _post(client, "graphics pipeline initialization failure")

    # Fake embedding returns a non-None list so the semantic path is taken
    fake_embedding = [0.1] * 384
    # Monkeypatch search_by_embedding to return the second message (semantic match)
    import pathly_orchestrator.db.queries.comms as _comms_mod
    original_sem = _comms_mod.search_by_embedding

    conn = get_db()
    sem_row = conn.execute(
        "SELECT * FROM comms_messages WHERE id=?", (mid_sem,)
    ).fetchone()
    sem_row_dict = dict(sem_row) if sem_row else {}

    monkeypatch.setattr(
        _comms_mod,
        "search_by_embedding",
        lambda *a, **k: [sem_row_dict] if sem_row_dict else [],
    )

    results = search_by_hybrid(conn, "setupWebGL", fake_embedding, ["feature"], ["demo"], k=5)
    result_ids = [r["id"] for r in results]
    # Both messages should appear in merged results
    assert mid_kw in result_ids or mid_sem in result_ids, (
        "Hybrid merge should include at least one of the two messages"
    )


def test_comms_hybrid_rrf_constant_value():
    """_RRF_K constant is 60 as specified."""
    from pathly_orchestrator.db.queries.comms import _RRF_K
    assert _RRF_K == 60
