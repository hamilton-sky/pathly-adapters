"""debug + quick-fix carry the same 3-tier retry ladder as the team flows.

`_resolve_feedback_target` returns the BASE agent unconditionally when a flow has no
`escalation_routing`, so a fix that kept failing verification routed back to `builder`
forever — no round-3 hand-off, no round-4 human backstop; the run just burned its iteration
and cost caps. Both small flows now escalate to `scout` at round 3 (when the FIX keeps
failing, the suspect is the diagnosis/scope above it) and to the human past round 4, matching
team/team-build/test.

These drive the REAL route_feedback against the REAL packaged YAMLs, with the retry count
supplied the way the FSM supplies it — `STATE.json`'s `retry_count_by_key`.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest
import yaml

from pathly_orchestrator.fsm import route_feedback

LADDER = [(0, "builder"), (1, "builder"), (2, "scout"), (3, "human"), (5, "human")]


def _flow(name: str) -> dict:
    return yaml.safe_load(
        files("pathly_data")
        .joinpath(f"core/flows/{name}.flow.yaml")
        .read_text(encoding="utf-8")
    )


def _route(tmp_path, flow: str, filename: str, retry_count: int | None) -> dict | None:
    storage = tmp_path / "pathly" / "features" / "topic-a"
    (storage / "feedback").mkdir(parents=True, exist_ok=True)
    (storage / "feedback" / filename).write_text("still failing\n", encoding="utf-8")
    if retry_count is not None:
        (storage / "STATE.json").write_text(
            json.dumps(
                {
                    "current": "VERIFYING",
                    "retry_count_by_key": {f"conv-1:{filename}": retry_count},
                }
            ),
            encoding="utf-8",
        )
    return route_feedback(_flow(flow), storage)


@pytest.mark.parametrize("retry_count,expected", LADDER)
def test_debug_verify_failures_climbs_the_ladder(tmp_path, retry_count, expected):
    assert (
        _route(tmp_path, "debug", "VERIFY_FAILURES.md", retry_count)["target_agent"]
        == expected
    )


@pytest.mark.parametrize("retry_count,expected", LADDER)
def test_quick_fix_test_failures_climbs_the_ladder(tmp_path, retry_count, expected):
    assert (
        _route(tmp_path, "quick-fix", "TEST_FAILURES.md", retry_count)["target_agent"]
        == expected
    )


@pytest.mark.parametrize("flow", ["debug", "quick-fix", "team", "team-build", "test"])
def test_every_flow_with_a_failure_loop_has_a_human_backstop(tmp_path, flow):
    """The point of the ladder: a persistently failing loop must eventually reach a person
    instead of retrying the same role until the cost cap ends the run."""
    assert _flow(flow).get("escalation_routing") or {}, f"{flow} has no ladder"


def test_without_any_count_source_the_ladder_starts_at_round_one(tmp_path):
    """No STATE.json and no injected counts -> attempt 1, the base agent. A caller that
    persists nothing gets round 1 forever, which is the failure mode the ladder exists to
    prevent — the count has to come from somewhere."""
    result = _route(tmp_path, "debug", "VERIFY_FAILURES.md", retry_count=None)
    assert result["target_agent"] == "builder"
    assert result["retry_count"] == 0


@pytest.mark.parametrize("retry_count,expected", LADDER)
def test_injected_counts_drive_the_same_ladder(tmp_path, retry_count, expected):
    """route_feedback also accepts the counts directly, so a caller that already holds
    them drives the identical ladder without a second read off disk."""
    storage = tmp_path / "pathly" / "features" / "topic-a"
    (storage / "feedback").mkdir(parents=True, exist_ok=True)
    (storage / "feedback" / "VERIFY_FAILURES.md").write_text("x\n", encoding="utf-8")
    result = route_feedback(
        _flow("debug"),
        storage,
        retry_counts={"VERIFY_FAILURES.md": retry_count},
    )
    assert result["target_agent"] == expected
    assert result["retry_count"] == retry_count
