"""Token counting is Strategy A — one per-adapter registry (`extract_tokens`).

Tokens are the universal, must-capture primitive; each engine reports them differently
(claude: result-envelope `usage` / `modelUsage`; codex: a JSONL usage event; antigravity:
nothing → a local char-based estimate). These tests pin each strategy plus the dispatch
contract (unknown adapter → claude/generic fallback; case-insensitive; never raises).
Cost is a SEPARATE concern (Strategy B, db/pricing.py) and is intentionally not tested here.
"""

import json

from pathly_orchestrator.runner.output import (
    estimate_tokens_from_text,
    extract_tokens,
)


def test_claude_lump_usage_folds_cache_tokens():
    payload = {
        "usage": {
            "input_tokens": 7,
            "cache_read_input_tokens": 226337,
            "cache_creation_input_tokens": 100,
            "output_tokens": 1630,
        }
    }
    tin, tout = extract_tokens("claude", payload, "")
    assert tin == 7 + 226337 + 100
    assert tout == 1630


def test_claude_falls_back_to_model_usage_when_lump_absent():
    payload = {
        "modelUsage": {
            "claude-haiku-4-5": {"inputTokens": 100, "outputTokens": 10},
            "claude-sonnet-4-6": {"inputTokens": 50, "outputTokens": 200},
        }
    }
    tin, tout = extract_tokens("claude", payload, "")
    assert tin == 150
    assert tout == 210


def test_codex_reads_tokens_from_jsonl_stream():
    # codex `exec --json` emits JSONL; a token-usage event carries the running total. The
    # claude envelope parser can't read this — codex needs its own strategy.
    # Codex/OpenAI report cached tokens INSIDE input_tokens and reasoning INSIDE output_tokens
    # (confirmed against live codex: total_tokens == input_tokens + output_tokens), so neither is
    # summed on top — doing so double-counts.
    stream = "\n".join(
        [
            json.dumps({"type": "item.started", "text": "working"}),
            json.dumps(
                {
                    "type": "token_count",
                    "input_tokens": 1200,
                    "cached_input_tokens": 300,
                    "output_tokens": 450,
                    "reasoning_output_tokens": 50,
                }
            ),
        ]
    )
    tin, tout = extract_tokens("codex", {}, stream)
    assert tin == 1200  # cached_input_tokens (300) already inside input_tokens — not added
    assert tout == 450  # reasoning_output_tokens (50) already inside output_tokens — not added


def test_agy_estimates_output_tokens_from_text():
    # antigravity emits no usage — estimate output tokens locally (~4 chars/token) so even
    # this engine yields a non-zero count instead of a misleading 0.
    text = "x" * 400
    tin, tout = extract_tokens("antigravity", {}, text)
    assert tin == 0
    assert tout == estimate_tokens_from_text(text) == 100


def test_agy_and_gemini_slugs_share_the_estimate_strategy():
    for slug in ("agy", "gemini"):
        tin, tout = extract_tokens(slug, {}, "hello world")
        assert tin == 0
        assert tout > 0


def test_unknown_adapter_falls_back_to_claude_parser():
    payload = {"usage": {"input_tokens": 5, "output_tokens": 3}}
    assert extract_tokens("some-future-cli", payload, "") == (5, 3)


def test_adapter_dispatch_is_case_insensitive():
    payload = {"usage": {"input_tokens": 5, "output_tokens": 3}}
    assert extract_tokens("CLAUDE", payload, "") == (5, 3)


def test_estimate_tokens_from_text_strips_ansi_and_handles_empty():
    assert estimate_tokens_from_text("") == 0
    assert estimate_tokens_from_text(None) == 0
    # ANSI escapes must not inflate the count.
    assert estimate_tokens_from_text("\x1b[31m" + "y" * 40 + "\x1b[0m") == 10


def test_extract_tokens_never_raises_on_garbage():
    # A strategy that trips over an unexpected shape must degrade to (0, 0), not propagate.
    assert extract_tokens("codex", {}, None) == (0, 0)
    assert extract_tokens("claude", None, "") == (0, 0)
