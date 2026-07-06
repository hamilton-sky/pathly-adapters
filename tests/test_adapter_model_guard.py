"""A model must match its engine. A Claude model on the Codex engine (or vice versa) is
rejected LOUDLY at dispatch — not left to 400 cryptically in the CLI mid-run
("The 'claude-sonnet-4-6' model is not supported when using Codex with a ChatGPT account"),
which silently produces no output.

Engine -> model families:
  claude       -> claude-*  (opus / sonnet / haiku / fable)
  codex        -> gpt-* / o1-* / o3-* / o4-* / o5-* / codex-*
  antigravity  -> gemini-*
  copilot      -> (multi-provider proxy — unconstrained)
"""

import pytest

from pathly_orchestrator.adapters import validate_adapter_model, resolve_command


def test_matching_models_pass():
    assert validate_adapter_model("claude", "claude-sonnet-4-6") is None
    assert validate_adapter_model("claude", "claude-opus-4-8") is None
    assert validate_adapter_model("codex", "gpt-5") is None
    assert validate_adapter_model("codex", "o4-mini") is None
    assert validate_adapter_model("antigravity", "gemini-2.5-pro") is None


def test_claude_model_on_codex_is_rejected_with_hint():
    err = validate_adapter_model("codex", "claude-sonnet-4-6")
    assert err is not None
    assert "codex" in err and "claude-sonnet-4-6" in err
    assert "claude" in err  # hints the engine the model DOES run on


def test_gpt_on_claude_and_gemini_on_codex_rejected():
    assert validate_adapter_model("claude", "gpt-5") is not None
    assert validate_adapter_model("codex", "gemini-2.5-pro") is not None


def test_empty_model_is_engine_default_ok():
    assert validate_adapter_model("codex", "") is None
    assert validate_adapter_model("claude", None) is None


def test_copilot_and_unknown_adapter_unconstrained():
    assert validate_adapter_model("copilot", "claude-sonnet-4-6") is None
    assert validate_adapter_model("nonsuch", "gpt-5") is None


def test_resolve_command_raises_loudly_on_mismatch():
    with pytest.raises(ValueError, match="adapter_model_mismatch"):
        resolve_command("codex", "do the thing", "claude-sonnet-4-6")
    # matching pair still builds argv
    out = resolve_command("claude", "do the thing", "claude-sonnet-4-6")
    assert "claude-sonnet-4-6" in out["argv"]
