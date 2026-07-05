"""Relevance gate on the Context channel (memory-consolidation phase).

Verifies _SEMANTIC_MAX_DISTANCE drops weak semantic hits and _CONTEXT_CHAR_BUDGET
caps the channel body — by injecting rows with controlled `_distance` values.
"""

from __future__ import annotations


def _stub_common(monkeypatch):
    import pathly_orchestrator.db.queries.comms as cq
    import pathly_orchestrator.runner.embeddings as emb

    # No governance, so only the Context channel matters.
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
            {
                "id": "strong",
                "text": "STRONG relevant match",
                "from_agent": "a",
                "to_agent": "*",
                "_distance": 0.20,
            },
            {
                "id": "weak",
                "text": "WEAK unrelated match",
                "from_agent": "b",
                "to_agent": "*",
                "_distance": 0.95,
            },  # > 0.75 cutoff → dropped
        ]

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)

    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "find the thing",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "STRONG relevant match" in block
    assert "WEAK unrelated match" not in block, "weak semantic hit must be gated out"


def test_keyword_hit_without_distance_is_kept(monkeypatch):
    """A row with no `_distance` (keyword/recency) is never dropped by the gate."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        return [
            {
                "id": "kw",
                "text": "keyword lexical match",
                "from_agent": "a",
                "to_agent": "*",
            }
        ]  # no _distance key

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)
    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "keyword lexical match" in block


def test_keyword_hit_dropped_on_cross_tier(monkeypatch):
    """CT4: a keyword/recency hit (no _distance) is kept on the feature board but dropped
    on cross-tier project/global boards — closing the per-tier-gate bypass (ISSUE-1b)."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        b = boards[0]
        return [
            {
                "id": f"{b}-kw",
                "text": f"{b} keyword only",
                "from_agent": "a",
                "to_agent": "*",
            }  # no _distance key → keyword/recency hit
        ]

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)
    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": True, "project": True, "global": True},
    )
    assert "feature keyword only" in block  # own board keeps keyword hits
    assert "project keyword only" not in block  # cross-tier keyword hit dropped
    assert "global keyword only" not in block


def test_per_tier_gate_drops_midrange_cross_tier(monkeypatch):
    """CT1: a 0.60 match is kept on the feature board (cutoff 0.75) but dropped on the
    project (0.55) and global (0.50) boards — cross-tier requires a stricter distance."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        b = boards[0]
        return [
            {
                "id": f"{b}-mid",
                "text": f"{b} midrange match",
                "from_agent": "a",
                "to_agent": "*",
                "_distance": 0.60,
            }
        ]

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)
    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": True, "project": True, "global": True},
    )
    assert "feature midrange match" in block  # 0.60 <= 0.75
    assert "project midrange match" not in block  # 0.60 > 0.55
    assert "global midrange match" not in block  # 0.60 > 0.50


def test_per_tier_gate_keeps_close_cross_tier(monkeypatch):
    """CT1: a genuinely-close project match (0.50 <= 0.55) still passes the project gate."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        b = boards[0]
        return [
            {
                "id": f"{b}-close",
                "text": f"{b} close match",
                "from_agent": "a",
                "to_agent": "*",
                "_distance": 0.50,
            }
        ]

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)
    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": False, "project": True, "global": False},
    )
    assert "project close match" in block  # 0.50 <= 0.55 project cutoff


def test_confidence_label_buckets():
    """CT2: _confidence_label maps distance to coarse buckets, empty for None."""
    from pathly_orchestrator.runner.comms_formatters import _confidence_label

    assert _confidence_label(None) == ""
    assert _confidence_label(0.30) == "match: strong"
    assert _confidence_label(0.55) == "match: strong"
    assert _confidence_label(0.68) == "match: moderate"
    assert _confidence_label(0.90) == "match: weak"


def test_confidence_bucket_shown_for_semantic_not_keyword(monkeypatch):
    """CT2: semantic lines carry a confidence bucket (not a raw float); a keyword hit
    (no _distance) carries none."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    def fake_hybrid(conn, text, emb_vec, boards, scopes, k):
        return [
            {
                "id": "s",
                "text": "strong semantic match",
                "from_agent": "a",
                "to_agent": "*",
                "_distance": 0.30,
            },
            {
                "id": "m",
                "text": "moderate semantic match",
                "from_agent": "b",
                "to_agent": "*",
                "_distance": 0.68,
            },
            {
                "id": "k",
                "text": "keyword only match",
                "from_agent": "c",
                "to_agent": "*",
            },  # no _distance
        ]

    monkeypatch.setattr(cq, "search_by_hybrid", fake_hybrid)
    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "match: strong" in block
    assert "match: moderate" in block
    assert "0.30" not in block and "0.68" not in block  # no raw floats leak
    # The keyword line is present but tagged with no confidence bucket.
    assert "keyword only match" in block


def test_context_char_budget_truncates(monkeypatch):
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    big = "x" * 900
    rows = [
        {
            "id": f"m{i}",
            "text": f"{big}-{i}",
            "from_agent": "a",
            "to_agent": "*",
            "_distance": 0.2,
        }
        for i in range(3)
    ]
    monkeypatch.setattr(cq, "search_by_hybrid", lambda *a, **k: rows)

    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "omitted" in block, "channel body should be capped by _CONTEXT_CHAR_BUDGET"
    assert len(block) < 3 * 900  # not all three full messages rendered
