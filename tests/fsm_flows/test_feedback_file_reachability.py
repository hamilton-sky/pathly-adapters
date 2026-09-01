"""A feedback file a flow can actually produce must be ROUTED by that flow.

`route_feedback` has a catch-all: any `.md` in `feedback/` that no `feedback_routing`
key matches returns `target_agent: "human"` with "Unrecognized feedback file: X. Review
and resolve manually." That fallback is a safety net, not a destination — reaching it means
the flow escalates to a person instead of routing to the role that can fix the problem, and
on the compiled executor (supervisor/compiled_flow.py) a `human` target fails the run
outright with `error_kind="human_checkpoint"`.

Two flows were reaching it on their own normal paths:

- `debug` never routed `VERIFY_FAILURES.md`, which its OWN VERIFYING skill
  (`debug/verify.md`) writes whenever verification fails — the flow's primary failure path,
  and `debug` is one of the two flows opted into `flow.compiled_executors`.
- The three consultation flows never routed `ARCH_FEEDBACK.md`, which `utilities/meet.md`
  writes into any feature (its option [1], captioned "routes to architect").

These tests drive the REAL `route_feedback` against the REAL packaged flow YAMLs, so they
fail if either regresses or a new flow repeats the pattern.
"""

from __future__ import annotations

from importlib.resources import files

import pytest
import yaml

from pathly_orchestrator.fsm import route_feedback


def _flow(name: str) -> dict:
    return yaml.safe_load(
        files("pathly_data")
        .joinpath(f"core/flows/{name}.flow.yaml")
        .read_text(encoding="utf-8")
    )


def _route(tmp_path, flow: str, filename: str) -> dict | None:
    storage = tmp_path / "pathly" / "features" / "topic-a"
    (storage / "feedback").mkdir(parents=True, exist_ok=True)
    (storage / "feedback" / filename).write_text("blocked\n", encoding="utf-8")
    return route_feedback(_flow(flow), storage)


def test_debug_routes_its_own_verify_failures(tmp_path):
    result = _route(tmp_path, "debug", "VERIFY_FAILURES.md")
    assert result is not None
    assert result["target_agent"] == "builder"
    assert "Unrecognized" not in result.get("instructions", "")


@pytest.mark.parametrize(
    "flow", ["consultation", "feature-consultation", "project-consultation"]
)
def test_consultation_flows_route_arch_feedback(tmp_path, flow):
    result = _route(tmp_path, flow, "ARCH_FEEDBACK.md")
    assert result is not None
    assert result["target_agent"] == "architect"


@pytest.mark.parametrize(
    "flow,filename",
    [
        ("debug", "VERIFY_FAILURES.md"),
        ("quick-fix", "TEST_FAILURES.md"),
        ("consultation", "ARCH_FEEDBACK.md"),
        ("team", "REVIEW_FAILURES.md"),
        ("team-build", "BUILD_FAILURES.md"),
        ("test", "TEST_FAILURES.md"),
    ],
)
def test_no_flow_falls_through_to_the_unrecognized_fallback(tmp_path, flow, filename):
    """The catch-all must stay a net for genuinely unknown files, never the path a
    flow's ordinary failure takes."""
    result = _route(tmp_path, flow, filename)
    assert result is not None
    assert (
        result["target_agent"] != "human"
    ), f"{flow} routes {filename} to a human: {result.get('instructions', '')}"


def test_the_fallback_still_catches_a_genuinely_unknown_file(tmp_path):
    """Guard the assertions above from passing because the fallback was removed."""
    result = _route(tmp_path, "debug", "TOTALLY_MADE_UP.md")
    assert result is not None
    assert result["target_agent"] == "human"
    assert "Unrecognized feedback file" in result["instructions"]
