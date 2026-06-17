"""3-tier feedback escalation (fsm.engine.route_feedback).

A failure file's target climbs as the same loop keeps failing:
  rounds 1-2 → the owner (builder) · round 3 → the upstream specialist
  (planner/po) · round 4+ → the human. Clarification files never tier.
"""
from __future__ import annotations

import json

from pathly_orchestrator.fsm.engine import _resolve_feedback_target, route_feedback

ESC = {"REVIEW_FAILURES": "planner", "TEST_FAILURES": "po"}


# ── pure ladder ──────────────────────────────────────────────────────────────

def test_owner_on_rounds_1_and_2():
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 0, ESC) == "builder"
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 1, ESC) == "builder"


def test_specialist_on_round_3():
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 2, ESC) == "planner"
    assert _resolve_feedback_target("TEST_FAILURES.md", "builder", 2, ESC) == "po"


def test_human_on_round_4_plus():
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 3, ESC) == "human"
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 9, ESC) == "human"


def test_clarification_never_tiers():
    # No escalation_routing entry → always the owner, regardless of retry count.
    assert _resolve_feedback_target("IMPL_QUESTIONS.md", "planner", 5, ESC) == "planner"
    assert _resolve_feedback_target("ACCEPTANCE_QUESTION.md", "po", 9, ESC) == "po"


def test_no_escalation_routing_is_backward_compatible():
    # A flow with no escalation_routing never tiers — old flows are unaffected.
    assert _resolve_feedback_target("REVIEW_FAILURES.md", "builder", 9, {}) == "builder"


# ── route_feedback integration ───────────────────────────────────────────────

def test_route_feedback_escalates_with_injected_counts(tmp_path):
    fb = tmp_path / "feedback"
    fb.mkdir()
    (fb / "REVIEW_FAILURES.md").write_text("reviewer: still broken", encoding="utf-8")
    flow = {"feedback_routing": {"REVIEW_FAILURES": "builder"}, "escalation_routing": ESC}

    assert route_feedback(flow, tmp_path, retry_counts={"REVIEW_FAILURES.md": 0})["target_agent"] == "builder"
    assert route_feedback(flow, tmp_path, retry_counts={"REVIEW_FAILURES.md": 2})["target_agent"] == "planner"

    r = route_feedback(flow, tmp_path, retry_counts={"REVIEW_FAILURES.md": 3})
    assert r["target_agent"] == "human"
    assert "broken" in r.get("instructions", ""), "human escalation includes the file content"


def test_route_feedback_reads_retry_from_state_json(tmp_path):
    fb = tmp_path / "feedback"
    fb.mkdir()
    (fb / "TEST_FAILURES.md").write_text("tester: criteria fail", encoding="utf-8")
    (tmp_path / "STATE.json").write_text(
        json.dumps({"retry_count_by_key": {"conv-2:TEST_FAILURES.md": 2}}), encoding="utf-8"
    )
    flow = {"feedback_routing": {"TEST_FAILURES": "builder"}, "escalation_routing": ESC}
    # No retry_counts passed → route_feedback reads STATE.json → round 3 → po.
    assert route_feedback(flow, tmp_path)["target_agent"] == "po"


# ── flow declares the escalation ─────────────────────────────────────────────

def test_team_build_flow_declares_escalation():
    from importlib.resources import files
    import yaml
    flow = yaml.safe_load(
        files("pathly_data").joinpath("core/flows/team-build.flow.yaml").read_text(encoding="utf-8")
    )
    esc = flow["escalation_routing"]
    assert esc["REVIEW_FAILURES"] == "planner"
    assert esc["TEST_FAILURES"] == "po"
    assert flow["feedback_routing"]["ACCEPTANCE_QUESTION"] == "po"
