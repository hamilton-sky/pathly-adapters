"""Governance block ordering — decisions render newest-first with explicit precedence.

Reconstructs the exact collision that corrupted the `local-usage-meter` board: eight
decisions made across a single afternoon, rendered oldest-first at day granularity, so
every bullet read as an indistinguishable "13d ago" and a builder could not tell that
"Phase 1 is unblocked" (17:20) came AFTER "remains a hard human gate" (15:05).

Rendering-level only. The real close is supersession (`superseded_by` via
POST /comms/supersede) -- see docs/BOARD_LIFECYCLE_FINDINGS.md Proposal A. Until an agent
path actually calls it, recency is the only signal the reader has, so these assertions
pin the signal being legible.
"""

from __future__ import annotations

GATE = "ARCH_QUESTION 2 remains a hard human gate before P1 BUILD"
UNBLOCK = "Adopt Option B. Phase 1 is fully unblocked."
ESCALATION = "Human checkpoint required - HUMAN_QUESTIONS.md"

# Same afternoon, ~2h apart: day-granularity ages cannot order these.
TS_GATE = "2026-08-10T15:05:00"
TS_UNBLOCK = "2026-08-10T17:20:00"
TS_ESCALATION = "2026-08-10T09:21:00"


def _decision(text: str, ts: str) -> dict:
    return {"id": ts, "text": text, "ts": ts, "board": "feature", "from_agent": "a"}


def _render(monkeypatch, decisions, escalations=()):
    import pathly_orchestrator.db.queries.comms as cq
    import pathly_orchestrator.runner.comms_context as cc
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(cq, "get_pending_decisions", lambda *a, **k: list(decisions))
    monkeypatch.setattr(cq, "get_active_escalations", lambda *a, **k: list(escalations))
    # No semantic channel -- governance is what's under test.
    monkeypatch.setattr(emb, "embed", lambda t: None)
    monkeypatch.setattr(cq, "search_by_hybrid", lambda *a, **k: [])
    return cc.retrieve_board_context(
        "feat",
        "C:/p",
        "implement phase 1",
        board_scope={"feature": True, "project": False, "global": False},
    )


def test_newest_decision_renders_before_the_older_one(monkeypatch):
    """get_pending_decisions returns ts ASC; the block must invert it."""
    block = _render(
        monkeypatch,
        [_decision(GATE, TS_GATE), _decision(UNBLOCK, TS_UNBLOCK)],  # ASC, as the query returns
    )
    assert block.index(UNBLOCK) < block.index(GATE), "17:20 decision must precede the 15:05 one"


def test_newest_decision_is_marked_latest(monkeypatch):
    block = _render(
        monkeypatch, [_decision(GATE, TS_GATE), _decision(UNBLOCK, TS_UNBLOCK)]
    )
    latest_line = next(line for line in block.splitlines() if "LATEST" in line)
    assert UNBLOCK in latest_line
    assert block.count("LATEST") == 1, "exactly one decision can be the latest"


def test_same_day_decisions_carry_minute_precision_stamps(monkeypatch):
    """The whole defect: "13d ago" on both. Minute stamps are what makes them orderable."""
    block = _render(
        monkeypatch, [_decision(GATE, TS_GATE), _decision(UNBLOCK, TS_UNBLOCK)]
    )
    assert "2026-08-10 15:05" in block
    assert "2026-08-10 17:20" in block


def test_precedence_rule_is_stated_explicitly(monkeypatch):
    block = _render(monkeypatch, [_decision(UNBLOCK, TS_UNBLOCK)])
    assert "NEWEST FIRST" in block
    assert "listed FIRST wins" in block


def test_decision_newer_than_open_escalation_warns_the_gate_stays_open(monkeypatch):
    """An agent decision claiming to resolve a human gate leaves BOTH on the board."""
    block = _render(
        monkeypatch,
        [_decision(UNBLOCK, TS_UNBLOCK)],
        [_decision(ESCALATION, TS_ESCALATION)],
    )
    assert "does NOT close a human gate" in block
    assert "treat the gate as OPEN" in block.replace("\n", " ")


def test_no_gate_warning_when_the_escalation_is_the_newer_message(monkeypatch):
    """Nothing claims to have resolved it yet, so the note would be noise."""
    block = _render(
        monkeypatch,
        [_decision(GATE, TS_GATE)],
        [_decision(ESCALATION, "2026-08-10T18:00:00")],
    )
    assert "does NOT close a human gate" not in block


def test_no_gate_warning_without_an_open_escalation(monkeypatch):
    block = _render(monkeypatch, [_decision(UNBLOCK, TS_UNBLOCK)], [])
    assert "does NOT close a human gate" not in block


def test_decision_missing_a_timestamp_does_not_crash_the_block(monkeypatch):
    block = _render(
        monkeypatch,
        [{"id": "x", "text": "no timestamp", "board": "feature"}, _decision(UNBLOCK, TS_UNBLOCK)],
    )
    assert "no timestamp" in block
    assert UNBLOCK in block
