"""Relevance gate on the 💡 Context channel (memory-consolidation phase).

Verifies _SEMANTIC_MAX_DISTANCE drops weak semantic hits and _CONTEXT_CHAR_BUDGET
caps the channel body — by injecting rows with controlled `_distance` values.
"""

from __future__ import annotations


def _stub_common(monkeypatch):
    import pathly_orchestrator.db.queries.comms as cq
    import pathly_orchestrator.runner.embeddings as emb

    # No governance, so only the 💡 channel matters.
    monkeypatch.setattr(cq, "get_pending_decisions", lambda *a, **k: [])
    monkeypatch.setattr(cq, "get_active_escalations", lambda *a, **k: [])
    # Non-None embedding so the semantic path runs (value unused — search is stubbed).
    monkeypatch.setattr(emb, "embed", lambda t: [0.0] * 384)
    return cq


def test_weak_semantic_hit_is_dropped(monkeypatch):
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        return [
            {"id": "strong", "text": "STRONG relevant match", "from_agent": "a",
             "to_agent": "*", "_distance": 0.20},
            {"id": "weak", "text": "WEAK unrelated match", "from_agent": "b",
             "to_agent": "*", "_distance": 0.95},  # > 0.75 cutoff → dropped
        ]

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)

    block = cc.retrieve_board_context(
        "feat", "C:/p", "find the thing",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "STRONG relevant match" in block
    assert "WEAK unrelated match" not in block, "weak semantic hit must be gated out"


def test_keyword_hit_without_distance_is_kept(monkeypatch):
    """A row with no `_distance` (keyword/recency) is never dropped by the gate."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        return [{"id": "kw", "text": "keyword lexical match", "from_agent": "a",
                 "to_agent": "*"}]  # no _distance key

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)
    block = cc.retrieve_board_context(
        "feat", "C:/p", "q",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "keyword lexical match" in block


def test_context_char_budget_truncates(monkeypatch):
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    big = "x" * 900
    rows = [
        {"id": f"m{i}", "text": f"{big}-{i}", "from_agent": "a", "to_agent": "*",
         "_distance": 0.2}
        for i in range(3)
    ]
    monkeypatch.setattr(cq, "search_by_hybrid", lambda *a, **k: rows)

    block = cc.retrieve_board_context(
        "feat", "C:/p", "q",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "omitted" in block, "channel body should be capped by _CONTEXT_CHAR_BUDGET"
    assert len(block) < 3 * 900  # not all three full messages rendered
