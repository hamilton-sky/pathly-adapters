"""Truncation-recovery for large claude ``--output-format=json`` envelopes (``output.parse_result``).

A big run (heavy cache reads → a large envelope) overflows the PTY tail buffer in ``terminal.ts``
(last ~500 chunks), so the retained ``stdout_tail`` starts mid-object with its opening brace gone.
The structured JSON parse then falls back to an inner ``modelUsage`` entry and reads cost=0/tokens=0
— which is why a headless board single-agent run recorded ``$0`` despite really costing $1.25.
``parse_result`` regex-recovers the numbers from the raw text when the structured parse yields 0.
"""

from pathly_orchestrator.runner.output import (
    _recover_truncated_claude_usage,
    parse_result,
)

# A real truncated tail: the top-level object's opening brace is gone; only the tail with the
# per-model modelUsage entry survives (mirrors the board single-agent run that recorded $0).
_TRUNCATED = (
    'sonnet-4-6":{"inputTokens":29,"outputTokens":17290,"cacheReadInputTokens":1916016,'
    '"cacheCreationInputTokens":69871,"webSearchRequests":0,"costUSD":1.2534678,'
    '"contextWindow":200000,"maxOutputTokens":32000}},"permission_denials":[],'
    '"terminal_reason":"completed","uuid":"c36a9aa1"}'
)

_FULL = (
    '{"type":"result","result":"hi","total_cost_usd":0.5,'
    '"usage":{"input_tokens":100,"output_tokens":50},'
    '"modelUsage":{"claude-sonnet-4-6":{"inputTokens":100,"outputTokens":50,"costUSD":0.5}}}'
)


def test_truncated_claude_envelope_recovers_cost_and_tokens():
    r = parse_result("claude", _TRUNCATED)
    assert abs(r["cost_usd"] - 1.2534678) < 1e-6
    assert r["tokens_in"] == 29 + 1916016 + 69871
    assert r["tokens_out"] == 17290


def test_full_envelope_uses_structured_parse_no_double_count():
    # A complete envelope must parse via the structured path — the regex recovery must not fire
    # and double the numbers (modelUsage costUSD 0.5 + total_cost_usd 0.5 would sum to 1.0).
    r = parse_result("claude", _FULL)
    assert abs(r["cost_usd"] - 0.5) < 1e-9
    assert r["tokens_in"] == 100
    assert r["tokens_out"] == 50


def test_recovery_helper_zeros_when_nothing_present():
    assert _recover_truncated_claude_usage("no json here") == (0, 0, 0)


def test_codex_adapter_skips_claude_recovery():
    # codex has its own JSONL usage path — the claude regex recovery must not fire for it.
    r = parse_result("codex", _TRUNCATED)
    assert r["cost_usd"] == 0.0
