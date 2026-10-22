"""chief-agent 20, B15: the escalation note ignores standing orders.

When the newest decision is newer than the newest open escalation, the governance block adds a
note that the decisions "may claim to resolve" the escalation and the gate stays open. The newest
decision was taken from all decisions, standing orders included, so a standing order the chief
posted after an escalation made the note appear, as if the order claimed to resolve it. Only the
ordinary decisions count now; the note itself is unchanged.
"""

from __future__ import annotations

from pathly_orchestrator.runner.comms_formatters import render_governance_lines
from pathly_orchestrator.runner.comms_governance import BINDING_MARK

NOTE = (
    "  NOTE: decisions above are newer than these escalations and may claim to "
    "resolve them. An agent decision does NOT close a human gate — only a human "
    "acknowledgement does. If a decision contradicts an open escalation, treat "
    "the gate as OPEN and say so rather than proceeding."
)


def _at(day: int) -> str:
    return f"2026-01-{day:02d}T12:00:00+00:00"


def _escalation(day: int) -> dict:
    return {
        "id": f"e{day}",
        "board": "feature",
        "type": "escalation",
        "text": "Need a human call on the schema.",
        "ts": _at(day),
    }


def _decision(day: int) -> dict:
    return {
        "id": f"d{day}",
        "board": "feature",
        "type": "decision",
        "text": "Use the new schema.",
        "ts": _at(day),
    }


def _standing(day: int) -> dict:
    return {
        **_decision(day),
        "id": f"s{day}",
        "board": "project",
        "to_agent": "*",
        "text": "Never push to master.",
        BINDING_MARK: True,
    }


def _lines(decisions: list[dict], escalations: list[dict]) -> list[str]:
    block = render_governance_lines(decisions, escalations)
    return "\n".join(block).split("\n")


def test_an_escalation_then_only_a_standing_order_has_no_note():
    lines = _lines([_standing(5)], [_escalation(3)])

    assert NOTE not in lines
    assert not [line for line in lines if "NOTE:" in line]
    assert any("BINDING for all roles: Never push to master." in x for x in lines)
    assert any("Open escalations" in line for line in lines)


def test_an_escalation_then_an_ordinary_decision_has_the_note_unchanged():
    lines = _lines([_decision(5)], [_escalation(3)])

    assert lines.count(NOTE) == 1


def test_an_escalation_a_standing_order_and_a_newer_ordinary_decision_has_the_note():
    lines = _lines([_standing(5), _decision(7)], [_escalation(3)])

    assert lines.count(NOTE) == 1


def test_a_standing_order_newer_than_an_older_ordinary_decision_has_no_note():
    lines = _lines([_decision(2), _standing(9)], [_escalation(5)])

    assert NOTE not in lines


def test_an_ordinary_decision_newer_than_a_standing_order_that_is_older_has_the_note():
    lines = _lines([_standing(2), _decision(9)], [_escalation(5)])

    assert lines.count(NOTE) == 1


def test_several_standing_orders_after_the_escalation_have_no_note():
    lines = _lines([_standing(5), _standing(6), _standing(7)], [_escalation(3)])

    assert NOTE not in lines


def test_a_decision_older_than_the_escalation_has_no_note():
    lines = _lines([_decision(2)], [_escalation(3)])

    assert NOTE not in lines


def test_the_newest_escalation_is_the_one_the_decision_is_compared_with():
    lines = _lines([_decision(5)], [_escalation(3), _escalation(8)])

    assert NOTE not in lines


def test_decisions_without_any_escalation_have_no_note():
    lines = _lines([_decision(5), _standing(6)], [])

    assert not [line for line in lines if "NOTE:" in line]
