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
