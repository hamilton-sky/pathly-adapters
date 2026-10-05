"""DESIGN_QUESTIONS.md routes to the architect in EVERY flow that routes it at all.

The filename used to carry two meanings: `team`/`test` treated it as the builder's
[ARCH]-tagged technical blocker (-> architect), while `team-build` and the three
consultation flows treated it as "questions for the designer" (-> designer). Both readings
were self-consistent, but the file has exactly one writer-side contract — team/build.md and
development/build.md both write it [ARCH]-tagged, and utilities/meet.md tells the user it
"routes to architect" regardless of the feature's flow. One filename, one meaning; the
designer keeps DESIGN_FEEDBACK.md.

These tests read the PACKAGED flow YAMLs, so they fail if a new flow reintroduces the split.
"""

from __future__ import annotations

from importlib.resources import files

import pytest
import yaml

FLOWS = [
    "consultation",
    "debug",
    "explore",
    "feature-consultation",
    "project-consultation",
    "quick-fix",
    "team",
    "team-build",
    "test",
]


def _routing(flow: str) -> dict:
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text).get("feedback_routing", {}) or {}


@pytest.mark.parametrize("flow", FLOWS)
def test_design_questions_always_routes_to_architect(flow):
    routing = _routing(flow)
    if "DESIGN_QUESTIONS" not in routing:
        pytest.skip(f"{flow} does not route DESIGN_QUESTIONS")
    assert routing["DESIGN_QUESTIONS"] == "architect"


def test_the_split_is_actually_gone():
    """Guard the parametrized test above from silently degrading to all-skips."""
    targets = {
        flow: _routing(flow)["DESIGN_QUESTIONS"]
        for flow in FLOWS
        if "DESIGN_QUESTIONS" in _routing(flow)
    }
    assert len(targets) == 6, f"expected 6 routing flows, got {sorted(targets)}"
    assert set(targets.values()) == {"architect"}


@pytest.mark.parametrize("flow", FLOWS)
def test_designer_keeps_an_inbound_file_wherever_a_designer_runs(flow):
    """Routing DESIGN_QUESTIONS away from the designer must not strand the role: every
    flow with a designer stage still has DESIGN_FEEDBACK.md pointed at them."""
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    config = yaml.safe_load(text)
    roles = set((config.get("role_map") or {}).values())
    if "designer" not in roles:
        pytest.skip(f"{flow} has no designer stage")
    assert (config.get("feedback_routing") or {}).get("DESIGN_FEEDBACK") == "designer"
