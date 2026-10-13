"""Validity tests for the two-flow split — team-build + consultation flows.

Ensures the new seed flows parse, start at the right state, route feedback to the
specialist roles, and that every agent_map skill actually exists as a core skill
(agent_map entries are loaded as prompts, so a missing skill would break a stage).
"""

from __future__ import annotations

from importlib.resources import files

import yaml


def _load(flow_name: str) -> dict:
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow_name}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _skill_exists(skill: str) -> bool:
    return files("pathly_data").joinpath(f"core/skills/{skill}.md").is_file()


def test_team_build_flow_valid():
    flow = _load("team-build")
    assert flow["flow"] == "team-build"
    # FSM starts a fresh run at the FIRST state (fsm/engine.py) — must be BUILDING.
    assert flow["states"][0] == "BUILDING"
    assert flow["states"][-1] == "DONE"
    for state, skill in flow["agent_map"].items():
        assert _skill_exists(
            skill
        ), f"agent_map[{state}]={skill!r} has no core skill file"
    fr = flow["feedback_routing"]
    assert fr["ARCH_QUESTION"] == "architect"
    # architect, not designer: DESIGN_QUESTIONS.md is the builder's [ARCH] blocker and
    # routes the same way in every flow. tests/fsm_flows/test_design_questions_routing.py
    # pins that uniformly; this line just keeps the two assertions from drifting apart.
    assert fr["DESIGN_QUESTIONS"] == "architect"
    assert fr["PO_QUESTIONS"] == "po"
    assert fr["IMPL_QUESTIONS"] == "planner"
    assert fr["REVIEW_FAILURES"] == "builder"
    assert fr["TEST_FAILURES"] == "builder"


def test_consultation_flow_valid():
    flow = _load("consultation")
    assert flow["flow"] == "consultation"
    assert flow["states"][0] == "PO_DISCUSSING"
    assert flow["states"][-1] == "DONE"
    for state, skill in flow["agent_map"].items():
        assert _skill_exists(
            skill
        ), f"agent_map[{state}]={skill!r} has no core skill file"
    # po → architect → researcher → designer → planner, in order.
    # Derive the sequence from `states` (not role_map dict-order): the FSM keys role_map
    # by state, so its dict-order is not meaningful, and the Studio flow editor serializes
    # keys alphabetically on save — asserting raw .values() order would break on a
    # round-trip through the editor while the actual flow is unchanged.
    role_seq = [flow["role_map"][s] for s in flow["states"] if s in flow["role_map"]]
    assert role_seq == [
        "po",
        "architect",
        "web-researcher",
        "designer",
        "planner",
    ]


def test_new_stage_skills_exist():
    assert _skill_exists("team/architect")
    assert _skill_exists("team/research")


def test_flows_load_via_fsm_loader():
    """The FSM _load_flow reads both new flows from the packaged files (project_root=None)."""
    from pathly_orchestrator.fsm_ops import _load_flow

    assert _load_flow("team-build")["flow"] == "team-build"
    assert _load_flow("consultation")["flow"] == "consultation"


def test_flow_config_roundtrips_escalation_and_custom_keys():
    """Decompose→assemble is lossless for escalation_routing AND arbitrary custom keys
    (the DB round-trip must not drop flow-level config)."""
    from pathly_orchestrator.db.queries.flow_defs import (
        _assemble_from_parts,
        _decompose_flow_dict,
    )

    flow = {
        "version": 1,
        "flow": "x",
        "storage_path": "p/{topic}/",
        "states": ["A", "B"],
        "transitions": {"A": ["B"], "B": []},
        "agent_map": {"A": "team/build"},
        "role_map": {"A": "builder"},
        "feedback_routing": {"REVIEW_FAILURES": "builder"},
        "escalation_routing": {"REVIEW_FAILURES": "planner", "TEST_FAILURES": "po"},
        "my_custom_key": {"anything": [1, 2]},
    }
    cfg, nodes, edges = _decompose_flow_dict(flow)
    assembled = _assemble_from_parts(cfg, nodes, edges)
    assert assembled["escalation_routing"] == {
        "REVIEW_FAILURES": "planner",
        "TEST_FAILURES": "po",
    }
    assert assembled["my_custom_key"] == {"anything": [1, 2]}
    assert assembled["feedback_routing"] == {"REVIEW_FAILURES": "builder"}


def test_team_build_escalation_survives_db_backed_load(tmp_path):
    """The real runtime path: _refresh_flows seeds team-build into the DB (decomposed),
    and _load_flow reassembles it WITH escalation_routing — i.e. the 3-tier feature is
    not silently dropped in production."""
    from pathly_orchestrator.fsm_ops import _load_flow

    flow = _load_flow("team-build", project_root=str(tmp_path))
    assert flow.get("escalation_routing", {}).get("REVIEW_FAILURES") == "planner"
    assert flow.get("escalation_routing", {}).get("TEST_FAILURES") == "po"


def _gate_on_fail_target(flow: dict, transition: str) -> str:
    """Role a gate's on_fail file routes to (via feedback_routing). 'human' ⇒ a headless
    run dead-ends there (human target is an error in headless mode)."""
    gates = flow.get("gates", {}).get(transition, [])
    assert gates, f"no gate on {transition}"
    on_fail = gates[0]["on_fail"]
    stem = on_fail[:-3] if on_fail.endswith(".md") else on_fail
    return flow.get("feedback_routing", {}).get(stem, "human")


def test_review_gate_does_not_deadend_headless():
    """Regression (goal run failed — subprocess): REVIEWING->TESTING used require_artifact on
    REVIEW.md, but NOTHING ever wrote REVIEW.md, and on_fail routed to HUMAN_QUESTIONS.md →
    human. So every headless team/team-build run died at the first review boundary. The gate
    must now verify REVIEW.md (which the reviewer writes on a clean pass) and route a miss back
    to the reviewer for a RE-REVIEW — never to a human checkpoint."""
    for flow_name in ("team-build", "team"):
        flow = _load(flow_name)
        gate = flow["gates"]["REVIEWING->TESTING"][0]
        assert gate["type"] == "verify_gate", flow_name
        assert gate["artifact"] == "REVIEW.md", flow_name
        assert gate["pass_marker"] == "RESULT: PASS", flow_name
        # The critical property: a missing/failed REVIEW.md re-reviews; it does NOT strand a
        # headless run at a human checkpoint the way the old require_artifact→human gate did.
        assert _gate_on_fail_target(flow, "REVIEWING->TESTING") == "reviewer", flow_name
