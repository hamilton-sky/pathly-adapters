"""Per-tier char budget on the Context channel (context_budget.py).

The channel used to charge ONE shared 2000-char budget in render order, and
`enabled_boards` renders feature first — so a chatty feature board spent the whole
allowance and the project/global entries, the expensive cross-cutting ones, were
dropped every time. These tests pin the split-and-pool behavior that replaced it.
"""

from __future__ import annotations

from pathly_orchestrator.runner.context_budget import (
    CONTEXT_CHAR_BUDGET,
    allocate_budget,
    select_within_budget,
)


def _stub_common(monkeypatch):
    import pathly_orchestrator.db.queries.comms as cq
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(cq, "get_pending_decisions", lambda *a, **k: [])
    monkeypatch.setattr(cq, "get_active_escalations", lambda *a, **k: [])
    monkeypatch.setattr(emb, "embed", lambda t: [0.0] * 384)
    return cq


def _row(mid: str, text: str) -> dict:
    return {
        "id": mid,
        "text": text,
        "from_agent": "a",
        "to_agent": "*",
        "_distance": 0.2,
    }


def test_chatty_feature_board_does_not_starve_cross_tier(monkeypatch):
    """The regression: 3 long feature notes must not consume project+global slots."""
    cq = _stub_common(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    big = "x" * 900
    per_board = {
        "feature": [_row(f"f{i}", f"{big}-{i}") for i in range(3)],
        "project": [_row("p1", "PROJECT-NOTE: the API contract is frozen")],
        "global": [_row("g1", "GLOBAL-NOTE: never log secrets")],
    }

    def _fake_search(conn, query_text, query_embedding, boards, scopes, k, **kw):
        return per_board.get(boards[0], [])

    monkeypatch.setattr(cq, "search_by_hybrid", _fake_search)

    block = cc.retrieve_board_context(
        "feat",
        "C:/p",
        "q",
        board_scope={"feature": True, "project": True, "global": True},
    )

    assert "PROJECT-NOTE" in block, "project tier starved by the feature board"
    assert "GLOBAL-NOTE" in block, "global tier starved by the feature board"
    # The feature board is still capped — not every long note fits.
    assert "omitted" in block


def test_feature_only_run_keeps_the_whole_budget():
    """A disabled tier's share is redistributed, never lost."""
    assert allocate_budget(["feature"]) == {"feature": CONTEXT_CHAR_BUDGET}
    two = allocate_budget(["feature", "project"])
    assert sum(two.values()) == CONTEXT_CHAR_BUDGET
    assert two["feature"] > two["project"]


def test_all_three_tiers_split_the_same_total():
    three = allocate_budget(["feature", "project", "global"])
    assert sum(three.values()) == CONTEXT_CHAR_BUDGET
    assert three["feature"] > three["project"] > three["global"]


def test_unknown_tier_names_fall_back_to_even_split():
    got = allocate_budget(["weird", "other"], total=100)
    assert got == {"weird": 50, "other": 50}


def test_at_least_one_entry_survives_an_oversized_line():
    """Mirrors the old `shown > 0` guarantee: never render an empty channel."""
    huge = ("feature", "y" * (CONTEXT_CHAR_BUDGET * 3))
    assert select_within_budget([huge], ["feature"]) == [0]


def test_unspent_tier_budget_is_pooled():
    """A quiet global tier funds a feature line that overflowed its own share."""
    entries = [("feature", "f" * 1400), ("global", "g" * 10)]
    kept = select_within_budget(entries, ["feature", "project", "global"])
    # feature's own share is 1000 — it only fits once project+global surplus is pooled.
    assert kept == [0, 1]


def test_render_order_is_preserved():
    entries = [("feature", "a" * 100), ("project", "b" * 100), ("global", "c" * 100)]
    assert select_within_budget(entries, ["feature", "project", "global"]) == [0, 1, 2]
