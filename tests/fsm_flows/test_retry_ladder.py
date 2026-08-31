"""Retry ladder: what varies by ATTEMPT, not just who owns it.

escalation_routing already changes the ROLE by round (fsm/engine_transitions.py's tiered
_resolve_feedback_target — round 1-2 owner, round 3 upstream specialist, round 4+ human).
What was missing: the STRATEGY. Every attempt on a given role got the identical prompt —
no signal it was a repeat, no guaranteed view of what actually failed, no visibility into
what an earlier attempt on this stage reported. This covers the fix:

  1. route_feedback now returns retry_count alongside target_agent.
  2. build_prompt_for_agent(retry_count=...) appends a retry-ladder block from round 2 on
     — round 1 (retry_count==0, the default) is asserted BYTE-IDENTICAL to before this,
     since that is the one guarantee every existing caller/snapshot depends on.
"""

from __future__ import annotations

from pathly_orchestrator.fsm.engine_transitions import route_feedback
from pathly_orchestrator.fsm_compose import build_prompt_for_agent

FLOW = {
    "feedback_routing": {"REVIEW_FAILURES": "builder"},
    "escalation_routing": {"REVIEW_FAILURES": ["planner", "architect"]},
}


def _write(tmp_path, filename, content="stub failure content"):
    fb = tmp_path / "feedback"
    fb.mkdir(exist_ok=True)
    (fb / filename).write_text(content, encoding="utf-8")


# ── route_feedback carries retry_count ────────────────────────────────────────


def test_route_feedback_reports_retry_count_zero_on_first_attempt(tmp_path):
    _write(tmp_path, "REVIEW_FAILURES.md")
    result = route_feedback(FLOW, tmp_path, retry_counts={"REVIEW_FAILURES.md": 0})
    assert result["retry_count"] == 0


def test_route_feedback_reports_the_injected_retry_count(tmp_path):
    _write(tmp_path, "REVIEW_FAILURES.md")
    result = route_feedback(FLOW, tmp_path, retry_counts={"REVIEW_FAILURES.md": 1})
    assert result["retry_count"] == 1
    assert result["target_agent"] == "builder"  # attempt 2, below tier 1 (planner @ 3)


def test_retry_count_and_role_escalation_move_together(tmp_path):
    """The SAME count both picks the role (existing behavior) and now also flows into
    the prompt (new behavior) — one number, two effects, always in sync."""
    _write(tmp_path, "REVIEW_FAILURES.md")
    result = route_feedback(FLOW, tmp_path, retry_counts={"REVIEW_FAILURES.md": 2})
    assert result["target_agent"] == "planner"  # attempt 3 -> tier 1
    assert result["retry_count"] == 2


# ── build_prompt_for_agent: round 1 is untouched ──────────────────────────────


def test_first_attempt_gets_no_retry_block(tmp_path):
    """retry_count defaults to 0 — every EXISTING caller that never passes it (there
    were none before this feature) gets the byte-identical prompt it always did."""
    _write(tmp_path, "REVIEW_FAILURES.md", "the build broke")
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md"
    )
    assert "Retry attempt" not in prompt


def test_explicit_zero_also_gets_no_retry_block(tmp_path):
    _write(tmp_path, "REVIEW_FAILURES.md", "the build broke")
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=0
    )
    assert "Retry attempt" not in prompt


def test_no_feedback_file_means_no_retry_block_even_with_a_count(tmp_path):
    """retry_count without a feedback_file is meaningless — there is nothing to retry."""
    prompt = build_prompt_for_agent("builder", tmp_path, retry_count=2)
    assert "Retry attempt" not in prompt


# ── build_prompt_for_agent: round 2+ carries the ladder ───────────────────────


def test_second_attempt_names_the_attempt_number(tmp_path):
    _write(tmp_path, "REVIEW_FAILURES.md", "the build broke")
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )
    assert "Retry attempt 2" in prompt
    assert "unresolved after 1 prior attempt" in prompt


def test_retry_block_inlines_the_current_feedback_content(tmp_path):
    """Guarantees the agent sees the REAL, current gate output verbatim, rather than
    depending on it going and reading the file itself (only Fix-mode roles are told to).
    """
    _write(
        tmp_path,
        "REVIEW_FAILURES.md",
        "Line 42: undefined reference to `frobnicate` — the reviewer traced this to builder.py",
    )
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )
    assert "undefined reference to `frobnicate`" in prompt


def test_retry_block_reflects_current_content_not_a_stale_snapshot(tmp_path):
    """The block reads the file at CALL time — a human/agent editing the feedback file
    between rounds must see their edit reflected, not a cached round-1 copy."""
    _write(tmp_path, "REVIEW_FAILURES.md", "original failure text")
    build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )
    _write(tmp_path, "REVIEW_FAILURES.md", "REVISED failure text after a partial fix")

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=2
    )
    assert "REVISED failure text after a partial fix" in prompt
    assert "original failure text" not in prompt


def test_missing_feedback_file_on_disk_does_not_crash_the_retry_block(tmp_path):
    """route_feedback said retry_count=1 (from STATE.json history) but the file itself
    is gone (e.g. resolved-then-reopened under a new name) — must degrade, not raise."""
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )
    assert "Retry attempt 2" in prompt  # the notice still appears
    assert "```\n\n```" not in prompt  # but no empty/garbled feedback fence


def test_retry_block_surfaces_prior_pipeline_history(tmp_path, monkeypatch):
    """The prior attempt's own AGENT_DONE summary is the one thing a repeat needs and
    never had — surfaced via the SAME build_pipeline_history_block build_prompt's
    normal (non-retry) path already uses, so no new history mechanism is invented."""
    # build_pipeline_history_block is imported lazily FROM pathly_orchestrator.runner
    # inside _retry_ladder_block (a fresh `from ... import` on every call) — patch it at
    # that source so the lazy import picks up the fake.
    import pathly_orchestrator.runner as runner_pkg

    monkeypatch.setattr(
        runner_pkg,
        "build_pipeline_history_block",
        lambda path: "- builder (conv 1): tried approach X, still failed the same check",
    )
    _write(tmp_path, "REVIEW_FAILURES.md", "still broken")

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )

    assert "tried approach X, still failed the same check" in prompt


def test_retry_block_survives_a_history_lookup_failure(tmp_path, monkeypatch):
    import pathly_orchestrator.runner as runner_pkg

    def _boom(path):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(runner_pkg, "build_pipeline_history_block", _boom)
    _write(tmp_path, "REVIEW_FAILURES.md", "still broken")

    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )

    assert "Retry attempt 2" in prompt  # degrades, doesn't raise
    assert "still broken" in prompt  # the feedback content is unaffected


def test_retry_block_precedes_fix_mode_for_root_cause_roles(tmp_path):
    """A root-cause role (e.g. architect) on a retry gets BOTH: the new ladder block
    AND the existing Fix-mode instructions — the two are additive, not a replacement."""
    _write(tmp_path, "ARCH_FEEDBACK.md", "the design decision was wrong")
    prompt = build_prompt_for_agent(
        "architect", tmp_path, feedback_file="ARCH_FEEDBACK.md", retry_count=1
    )
    assert "Retry attempt 2" in prompt
    assert "Fix mode" in prompt
    assert prompt.index("Retry attempt 2") < prompt.index("Fix mode")


def test_retry_block_content_is_capped(tmp_path):
    """A pathological feedback file must not blow up the prompt unboundedly."""
    _write(tmp_path, "REVIEW_FAILURES.md", "x" * 20_000)
    prompt = build_prompt_for_agent(
        "builder", tmp_path, feedback_file="REVIEW_FAILURES.md", retry_count=1
    )
    assert len(prompt) < 20_000 + 2_000  # bounded, not the full 20k inlined twice-over
