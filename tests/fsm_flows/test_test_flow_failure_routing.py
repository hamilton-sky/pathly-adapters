"""Phase 0 hygiene fix — test.flow.yaml routed TEST_FAILURES.md to TESTING (a
self-loop) instead of BUILDING, unlike every sibling flow (team.flow.yaml,
team-build.flow.yaml) and its own feedback_routing (TEST_FAILURES -> builder).

A self-loop (old_current == new_current) skips eventlog.write_state's transition
legality check entirely, so this didn't crash — it silently re-ran team/test against
unfixed code forever instead of ever handing the failure to the builder.
"""

from __future__ import annotations

from pathlib import Path

import pathly_data
import yaml

from pathly_orchestrator.fsm.engine_transitions import evaluate_transition_rules

_FLOWS_DIR = Path(pathly_data.__file__).parent / "core" / "flows"


def _load(name: str) -> dict:
    return yaml.safe_load((_FLOWS_DIR / name).read_text(encoding="utf-8"))


def test_test_flow_routes_test_failures_to_building(tmp_path):
    flow = _load("test.flow.yaml")
    (tmp_path / "TEST_FAILURES.md").write_text("x", encoding="utf-8")
    assert evaluate_transition_rules(flow, "TESTING", tmp_path) == "BUILDING"


def test_test_flow_transitions_declare_testing_to_building():
    """BUILDING must be a structurally allowed edge from TESTING — the fixed
    transition_rules routing target has to exist in `transitions`, or a non-self
    TESTING->BUILDING would be rejected by eventlog.write_state's legality check."""
    flow = _load("test.flow.yaml")
    assert "BUILDING" in flow["transitions"]["TESTING"]


def test_sibling_flows_agree_on_test_failures_routing():
    """team.flow.yaml, team-build.flow.yaml, and test.flow.yaml must route a
    TEST_FAILURES.md artifact to the same place: BUILDING."""
    for name, state in [
        ("team.flow.yaml", "TESTING"),
        ("team-build.flow.yaml", "TESTING"),
        ("test.flow.yaml", "TESTING"),
    ]:
        flow = _load(name)
        rule = flow["transition_rules"][state]
        assert rule["on_artifact"]["TEST_FAILURES.md"] == "BUILDING", name


def test_test_flow_has_escalation_routing_matching_siblings():
    """test.flow.yaml shares team/review + team/test skills with team.flow.yaml and
    team-build.flow.yaml but had NO escalation_routing at all — an empty
    escalation_routing makes _resolve_feedback_target unconditionally return the base
    agent, so a persistently failing review/test loop routed back to builder forever,
    with no round-3 upstream hand-off and no round-4 human escalation."""
    expected = {
        "REVIEW_FAILURES": "planner",
        "SCOPE_VIOLATION": "planner",
        "TEST_FAILURES": "po",
    }
    assert _load("test.flow.yaml")["escalation_routing"] == expected
    assert _load("team.flow.yaml")["escalation_routing"] == expected
    assert _load("team-build.flow.yaml")["escalation_routing"] == expected


def test_test_flow_review_failures_escalates_through_the_tiers():
    """Round 1-2 stays with the base agent (builder); round 3 hands off to planner
    (the upstream specialist); round 4+ escalates to human — exercised against
    test.flow.yaml's own escalation_routing via the real resolver."""
    from pathly_orchestrator.fsm.engine_transitions import _resolve_feedback_target

    esc = _load("test.flow.yaml")["escalation_routing"]
    assert (
        _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 0, esc) == "builder"
    )
    assert (
        _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 1, esc) == "builder"
    )
    assert (
        _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 2, esc) == "planner"
    )
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 3, esc) == "human"
