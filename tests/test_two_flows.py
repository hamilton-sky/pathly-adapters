"""Validity tests for the two-flow split — team-build + consultation flows.

Ensures the new seed flows parse, start at the right state, route feedback to the
specialist roles, and that every agent_map skill actually exists as a core skill
(agent_map entries are loaded as prompts, so a missing skill would break a stage).
"""
from __future__ import annotations

from importlib.resources import files

import yaml


def _load(flow_name: str) -> dict:
    text = files("pathly_data").joinpath(f"core/flows/{flow_name}.flow.yaml").read_text(encoding="utf-8")
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
        assert _skill_exists(skill), f"agent_map[{state}]={skill!r} has no core skill file"
    fr = flow["feedback_routing"]
    assert fr["ARCH_QUESTION"] == "architect"
    assert fr["DESIGN_QUESTIONS"] == "designer"
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
        assert _skill_exists(skill), f"agent_map[{state}]={skill!r} has no core skill file"
    # po → architect → researcher → designer → planner, in order
    assert list(flow["role_map"].values()) == [
        "po", "architect", "web-researcher", "designer", "planner",
    ]


def test_new_stage_skills_exist():
    assert _skill_exists("team/architect")
    assert _skill_exists("team/research")


def test_flows_load_via_fsm_loader():
    """The FSM _load_flow reads both new flows from the packaged files (project_root=None)."""
    from pathly_orchestrator.fsm_ops import _load_flow
    assert _load_flow("team-build")["flow"] == "team-build"
    assert _load_flow("consultation")["flow"] == "consultation"
