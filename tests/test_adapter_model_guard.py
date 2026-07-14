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


# ── Per-stage model reconciliation (supervisor loop) ─────────────────────────
# A flow's adapter_map can route ONE stage to a different engine than the run-level
# model belongs to (the consultation flow runs PO_DISCUSSING + DESIGNING on codex while
# the run model is claude-sonnet-4-6). The supervisor loop reconciles the model to the
# per-stage adapter via _stage_model_for so it never spawns a mismatched pair — which
# otherwise hard-crashes the loop (adapter_model_mismatch -> loop_crashed) and shows
# "decomposition failed" on the board.


def test_stage_model_for_drops_mismatched_model_to_engine_default():
    from pathly_orchestrator.supervisor.orchestrator import _stage_model_for

    # A claude model on a codex-routed stage falls back to codex's OWN default ("").
    assert _stage_model_for("codex", "claude-sonnet-4-6") == ""
    assert _stage_model_for("claude", "gpt-5") == ""


def test_stage_model_for_keeps_matching_model():
    from pathly_orchestrator.supervisor.orchestrator import _stage_model_for

    assert _stage_model_for("claude", "claude-sonnet-4-6") == "claude-sonnet-4-6"
    assert _stage_model_for("codex", "gpt-5.4") == "gpt-5.4"


def test_stage_model_for_preserves_empty_and_unconstrained_and_unknown():
    from pathly_orchestrator.supervisor.orchestrator import _stage_model_for

    assert _stage_model_for("codex", "") == ""  # already the engine default
    # copilot is an unconstrained proxy — never drop its model.
    assert _stage_model_for("copilot", "claude-sonnet-4-6") == "claude-sonnet-4-6"
    # An unknown/custom model is NOT dropped (don't guess which engine it belongs to).
    assert _stage_model_for("codex", "some-custom-model") == "some-custom-model"


def test_reconciled_pair_no_longer_raises_in_resolve_command():
    """End-to-end: reconcile the codex stage, then resolve_command must build cleanly
    instead of raising adapter_model_mismatch (the crash the consultation hit)."""
    from pathly_orchestrator.supervisor.orchestrator import _stage_model_for

    reconciled = _stage_model_for("codex", "claude-sonnet-4-6")  # -> ""
    out = resolve_command("codex", "do the thing", reconciled)  # must NOT raise
    assert out["argv"]  # built without a --model flag (engine default)
    assert "claude-sonnet-4-6" not in out["argv"]
