"""Tests for HQ's read-only guardrails (hq-copilot ticket 04).

No real model is invoked anywhere here: the tool assertion is tested by
mutating the schema tuple, and the refusal pre-check is tested via a
counting stub for build_hq_turn (what prepare_hq_turn calls to build the
model turn).
"""

from __future__ import annotations

import pytest

SCOPE = "hqguard"


def _stub_build(monkeypatch, calls: list):
    from pathly_orchestrator import hq_prompt

    def _counting(
        user_message, board_id, project_root=None, budget_tokens=None, sections=None
    ):
        calls.append((user_message, board_id))
        return hq_prompt.HQTurn("SYSTEM", "PROMPT")

    monkeypatch.setattr(hq_prompt, "build_hq_turn", _counting)


def test_hq_tools_assertion_fails_loudly(monkeypatch):
    from pathly_orchestrator import hq_prompt

    monkeypatch.setattr(hq_prompt, "HQ_TOOL_SCHEMAS", ({"name": "evil"},))
    with pytest.raises(AssertionError):
        hq_prompt.build_hq_prompt("hi", SCOPE)


@pytest.mark.parametrize(
    "msg",
    [
        "stop the run",
        "restart the builder",
        "answer the question",
        "approve it",
        "Please RETRY the failed stage",
        "pause the planner",
        "can you restart the builder?",
        "The builder is stuck. Restart it.",
        "let's rerun the failed stage",
        "please, stop the run",
        "hq, approve it",
        "what's stuck? also restart the builder",
        "I want you to cancel the pipeline",
    ],
)
def test_action_patterns_redirect_without_model(msg, monkeypatch):
    from pathly_orchestrator import hq_prompt

    calls: list = []
    _stub_build(monkeypatch, calls)
    turn = hq_prompt.prepare_hq_turn(msg, SCOPE)
    assert turn.redirect == hq_prompt.HQ_READONLY_REDIRECT
    assert calls == []  # zero model invocations


@pytest.mark.parametrize(
    "msg",
    [
        "should I stop the builder?",
        "Should we restart the run?",
        "what needs my attention?",
        "is the builder running?",
        "who started the run?",
        # A status question that merely mentions an action verb is not an
        # action request: refusing these would break the copilot's core job.
        "why did the build stop?",
        "did the planner answer the question?",
        "when will the run start?",
        "what happens if I pause the run?",
        "is it safe to retry the stage?",
        "Stop.",
    ],
)
def test_non_action_messages_reach_model(msg, monkeypatch):
    from pathly_orchestrator import hq_prompt

    calls: list = []
    _stub_build(monkeypatch, calls)
    turn = hq_prompt.prepare_hq_turn(msg, SCOPE)
    assert turn.redirect is None
    assert turn.prompt == "PROMPT"
    assert calls == [(msg, SCOPE)]


def test_advisory_reaches_model_not_redirect(monkeypatch):
    # The ticket's explicit carve-out: advisory phrasing goes to the model,
    # which may discuss but not act.
    from pathly_orchestrator import hq_prompt

    calls: list = []
    _stub_build(monkeypatch, calls)
    turn = hq_prompt.prepare_hq_turn("should I stop the builder?", SCOPE)
    assert turn.redirect is None
    assert hq_prompt.HQ_READONLY_REDIRECT not in turn.text
