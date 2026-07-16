"""Smart fix-routing (pathly/features/smart-fix-routing/DESIGN.md).

Unit tests for two pieces:
  - ``route_feedback``'s optional ``feedback_priority`` sort (ss1.5 — upstream-first
    ordering, opt-in, fallback = today's dict-order behavior).
  - ``build_prompt_for_agent``'s fix-mode block (ss3.1 — appended only for a routed
    root-cause role: po/planner/architect/designer).
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.fsm.engine_transitions import route_feedback
from pathly_orchestrator.fsm_compose import build_prompt_for_agent

# ── route_feedback: filename -> role for each new tag/file ──────────────────

FLOW = {
    "feedback_routing": {
        "HUMAN_QUESTIONS": "human",
        "BLOCKED_ON_HUMAN": "human",
        "REQUIREMENT_GAP": "po",
        "PLAN_FEEDBACK": "planner",
        "ARCH_FEEDBACK": "architect",
        "DESIGN_FEEDBACK": "designer",
        "REVIEW_FAILURES": "builder",
        "TEST_FAILURES": "builder",
    },
    "feedback_priority": [
        "HUMAN_QUESTIONS",
        "BLOCKED_ON_HUMAN",
        "REQUIREMENT_GAP",
        "PLAN_FEEDBACK",
        "ARCH_FEEDBACK",
        "DESIGN_FEEDBACK",
        "REVIEW_FAILURES",
        "TEST_FAILURES",
    ],
}


def _write(tmp_path, filename, content="stub failure content"):
    fb = tmp_path / "feedback"
    fb.mkdir(exist_ok=True)
    (fb / filename).write_text(content, encoding="utf-8")


@pytest.mark.parametrize(
    "filename,expected_agent",
    [
        ("ARCH_FEEDBACK.md", "architect"),
        ("PLAN_FEEDBACK.md", "planner"),
        ("DESIGN_FEEDBACK.md", "designer"),
        ("REQUIREMENT_GAP.md", "po"),
    ],
)
def test_new_feedback_files_route_to_their_role(tmp_path, filename, expected_agent):
    _write(tmp_path, filename)
    result = route_feedback(FLOW, tmp_path)
    assert result["target_agent"] == expected_agent
    assert result["file"] == filename


def test_regression_review_failures_only_routes_builder(tmp_path):
    """Byte-identical to today: with only REVIEW_FAILURES.md open, target is builder —
    even though feedback_priority is declared on this flow."""
    _write(tmp_path, "REVIEW_FAILURES.md")
    result = route_feedback(FLOW, tmp_path)
    assert result["target_agent"] == "builder"
    assert result["file"] == "REVIEW_FAILURES.md"


def test_priority_arch_before_review_failures(tmp_path):
    """Upstream-first: both ARCH_FEEDBACK and REVIEW_FAILURES open -> the architect
    (root cause) is routed first per feedback_priority, not feedback_routing dict order."""
    _write(tmp_path, "REVIEW_FAILURES.md")
    _write(tmp_path, "ARCH_FEEDBACK.md")
    result = route_feedback(FLOW, tmp_path)
    assert result["target_agent"] == "architect"
    assert result["file"] == "ARCH_FEEDBACK.md"


def test_priority_requirement_gap_beats_everything(tmp_path):
    """REQUIREMENT_GAP is the most-upstream root cause in the canonical order — it wins
    even against ARCH_FEEDBACK, PLAN_FEEDBACK, DESIGN_FEEDBACK, and REVIEW_FAILURES."""
    for filename in (
        "REVIEW_FAILURES.md",
        "ARCH_FEEDBACK.md",
        "DESIGN_FEEDBACK.md",
        "PLAN_FEEDBACK.md",
        "REQUIREMENT_GAP.md",
    ):
        _write(tmp_path, filename)
    result = route_feedback(FLOW, tmp_path)
    assert result["target_agent"] == "po"
    assert result["file"] == "REQUIREMENT_GAP.md"


def test_no_priority_declared_falls_back_to_dict_order(tmp_path):
    """No feedback_priority on the flow -> first match in feedback_routing.items() order
    wins (today's behavior, unchanged) even though ARCH_FEEDBACK would sort earlier under
    the canonical priority — proves the new ordering is opt-in, not automatic."""
    flow_no_priority = {
        "feedback_routing": {
            # REVIEW_FAILURES declared FIRST in dict order, on purpose.
            "REVIEW_FAILURES": "builder",
            "ARCH_FEEDBACK": "architect",
        }
    }
    _write(tmp_path, "ARCH_FEEDBACK.md")
    _write(tmp_path, "REVIEW_FAILURES.md")
    result = route_feedback(flow_no_priority, tmp_path)
    assert result["target_agent"] == "builder"
    assert result["file"] == "REVIEW_FAILURES.md"


def test_priority_entry_absent_from_open_files_is_ignored(tmp_path):
    """A feedback_priority list may name files that aren't open — only open files compete."""
    _write(tmp_path, "REVIEW_FAILURES.md")
    result = route_feedback(FLOW, tmp_path)
    assert result["target_agent"] == "builder"


# ── build_prompt_for_agent: fix-mode block ───────────────────────────────────


def _feature_storage(tmp_path):
    storage_path = tmp_path / "pathly" / "features" / "my-feature"
    storage_path.mkdir(parents=True)
    return storage_path


def test_build_prompt_for_agent_architect_fix_mode(tmp_path):
    storage_path = _feature_storage(tmp_path)
    prompt = build_prompt_for_agent(
        "architect", storage_path, feedback_file="ARCH_FEEDBACK.md"
    )
    assert "## Fix mode — you are resolving a routed review/test failure" in prompt
    assert "ARCHITECTURE_PROPOSAL.md" in prompt
    assert "ARCH_FEEDBACK.md" in prompt
    assert "Do NOT run pathly-fsm-call / complete-stage" in prompt


@pytest.mark.parametrize(
    "role,artifact",
    [
        ("po", "USER_STORIES.md"),
        ("planner", "IMPLEMENTATION_PLAN.md"),
        ("architect", "ARCHITECTURE_PROPOSAL.md"),
        ("designer", "DESIGN.md"),
    ],
)
def test_build_prompt_for_agent_fix_mode_role_artifact_map(tmp_path, role, artifact):
    """Role -> artifact map from DESIGN.md ss3.1."""
    storage_path = _feature_storage(tmp_path)
    prompt = build_prompt_for_agent(role, storage_path, feedback_file="SOME_FEEDBACK.md")
    assert "## Fix mode" in prompt
    assert f"Correct YOUR artifact: {artifact}" in prompt


def test_build_prompt_for_agent_builder_path_unchanged(tmp_path):
    """The builder path is byte-identical whether or not feedback_file is passed —
    the hard regression constraint (task requirement #1)."""
    storage_path = _feature_storage(tmp_path)
    without_feedback = build_prompt_for_agent("builder", storage_path)
    with_feedback = build_prompt_for_agent(
        "builder", storage_path, feedback_file="REVIEW_FAILURES.md"
    )
    assert without_feedback == with_feedback
    assert "Fix mode" not in with_feedback


def test_build_prompt_for_agent_reviewer_and_human_never_get_fix_mode(tmp_path):
    """Only po/planner/architect/designer are root-cause roles — reviewer and human,
    which can also be routed a feedback file, never get the fix-mode block."""
    storage_path = _feature_storage(tmp_path)
    reviewer_prompt = build_prompt_for_agent(
        "reviewer", storage_path, feedback_file="REVIEW_INCOMPLETE.md"
    )
    assert "Fix mode" not in reviewer_prompt


def test_build_prompt_for_agent_no_feedback_file_is_unchanged_for_any_role(tmp_path):
    """feedback_file=None (the default) never appends fix mode, regardless of role —
    covers any caller that has not been updated to pass it."""
    storage_path = _feature_storage(tmp_path)
    prompt = build_prompt_for_agent("architect", storage_path)
    assert "Fix mode" not in prompt
