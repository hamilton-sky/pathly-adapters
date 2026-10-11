"""Cache-aware cost estimation.

Both token strategies fold cached tokens INTO tokens_in (claude: cache read + creation added;
codex: cached_input_tokens already inside input_tokens). Before this, Strategy B priced every
one of them at the full input rate — a ~3-4x overstatement on a heavily-cached codex run. These
tests pin: the cached subset is extracted per adapter, carried on BILLING_UPDATE, and priced at
the CACHE_RATES multiple of the input rate; models with no cache entry keep the flat price.
"""

import json

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.pricing import (
    PricingRegistry,
    cache_tokens_of,
    estimate_cost,
    estimate_cost_for,
)
from pathly_orchestrator.db.queries.fsm_events import append_event
from pathly_orchestrator.db.queries.invocation_projection import (
    backfill_invocations_from_events,
)
from pathly_orchestrator.runner.output import extract_cache_tokens, parse_result

PR = "C:/cache-proj"
M = 1_000_000


# ── Strategy B: pricing ──────────────────────────────────────────────────────────


def test_codex_cached_input_priced_at_tenth_of_input_rate():
    # gpt-5: $1.25 in / $10 out; cached input 0.1x → $0.125.
    cost, src = estimate_cost("gpt-5-codex", M, 0, cache_read_tokens=850_000)
    assert src == "estimated"
    assert cost == pytest.approx(0.15 * 1.25 + 0.85 * 0.125)


def test_claude_cache_read_and_write_multipliers():
    # sonnet-4: $3 in. 1M in = 100k fresh + 800k read (0.1x) + 100k write (1.25x).
    cost, _ = estimate_cost(
        "claude-sonnet-4-6",
        M,
        0,
        cache_read_tokens=800_000,
        cache_write_tokens=100_000,
    )
    assert cost == pytest.approx((0.1 + 0.8 * 0.1 + 0.1 * 1.25) * 3.0)


def test_no_cache_tokens_matches_flat_price():
    flat, _ = estimate_cost("gpt-5", 500_000, 100_000)
    assert flat == pytest.approx(0.5 * 1.25 + 0.1 * 10.0)


def test_model_without_cache_entry_keeps_flat_rate():
    # No verified cache rate for gemini → no discount invented.
    with_cache, _ = PricingRegistry().compute(
        "google", "gemini-2.5-pro", M, 0, cache_read_tokens=M
    )
    flat, _ = PricingRegistry().compute("google", "gemini-2.5-pro", M, 0)
    assert with_cache == flat


def test_cache_tokens_clamped_to_tokens_in():
    cost, _ = estimate_cost(
        "gpt-5", 1000, 0, cache_read_tokens=5000, cache_write_tokens=5000
    )
    assert cost == pytest.approx(1000 / M * 1.25 * 0.1)


def test_estimate_cost_for_adapter_slug_fallback_carries_cache():
    cost, src = estimate_cost_for("codex", M, 0, cache_read_tokens=M)
    assert src == "estimated"
    assert cost == pytest.approx(0.125)


def test_cache_tokens_of_tolerates_garbage():
    assert cache_tokens_of(None) == {"cache_read_tokens": 0, "cache_write_tokens": 0}
    assert cache_tokens_of({"cache_read_tokens": "x", "cache_write_tokens": -4}) == {
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    assert cache_tokens_of({"cache_read_tokens": 7})["cache_read_tokens"] == 7


# ── Strategy A: extracting the cached subset ─────────────────────────────────────


def test_claude_lump_usage_cache_split():
    payload = {
        "usage": {
            "input_tokens": 7,
            "cache_read_input_tokens": 226337,
            "cache_creation_input_tokens": 100,
            "output_tokens": 1630,
        }
    }
    assert extract_cache_tokens("claude", payload, "") == (226337, 100)


def test_claude_model_usage_cache_split():
    payload = {
        "modelUsage": {
            "claude-haiku-4-5": {"inputTokens": 1, "cacheReadInputTokens": 40},
            "claude-sonnet-4-6": {
                "cacheReadInputTokens": 60,
                "cacheCreationInputTokens": 5,
            },
        }
    }
    assert extract_cache_tokens("claude", payload, "") == (100, 5)


def test_claude_truncated_envelope_recovers_cache_split():
    tail = '"cacheReadInputTokens": 900, "cacheCreationInputTokens": 30, "outputTokens": 4}}'
    assert extract_cache_tokens("claude", {}, tail) == (900, 30)


def test_codex_cached_input_from_jsonl_stream():
    stream = "\n".join(
        [
            json.dumps({"type": "item.started"}),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 1200,
                        "cached_input_tokens": 1000,
                        "output_tokens": 40,
                    },
                }
            ),
        ]
    )
    assert extract_cache_tokens("codex", {}, stream) == (1000, 0)
    parsed = parse_result("codex", stream)
    assert parsed["tokens_in"] == 1200
    assert parsed["cache_read_tokens"] == 1000
    assert parsed["cache_write_tokens"] == 0


def test_codex_openai_style_cached_tokens_details():
    stream = json.dumps(
        {
            "usage": {
                "prompt_tokens": 500,
                "completion_tokens": 9,
                "prompt_tokens_details": {"cached_tokens": 400},
            }
        }
    )
    assert extract_cache_tokens("codex", {}, stream) == (400, 0)


def test_agy_reports_no_cache_and_never_raises():
    assert extract_cache_tokens("agy", {}, "hello") == (0, 0)
    assert extract_cache_tokens("claude", {"usage": "nope"}, "") == (0, 0)


# ── projection: BILLING_UPDATE carries the split into the estimate ───────────────


def _ad(model):
    return {
        "type": "AGENT_DONE",
        "agent": "builder",
        "conversation": 1,
        "cost_usd": 0.0,
        "model": model,
        "total_tokens": 0,
        "ts": "2026-10-11T12:00:00Z",
    }


def _billing(model, tin, tout, cache_read=0):
    return {
        "type": "BILLING_UPDATE",
        "agent": "builder",
        "conversation": 1,
        "cost_usd": 0.0,
        "model": model,
        "run_id": "run-c",
        "tokens_in": tin,
        "tokens_out": tout,
        "total_tokens": tin + tout,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": 0,
        "ts": "2026-10-11T12:01:00Z",
    }


def _cost(feature):
    return (
        get_db()
        .execute(
            "SELECT cost_usd, cost_source FROM agent_invocations "
            "WHERE project_root=? AND feature=?",
            (PR, feature),
        )
        .fetchone()
    )


def test_projection_prices_cached_codex_billing_at_cache_rate():
    conn = get_db()
    append_event(conn, PR, "f_cache", _ad("gpt-5-codex"))
    append_event(conn, PR, "f_cache", _billing("gpt-5-codex", M, 0, cache_read=900_000))
    row = _cost("f_cache")
    assert row["cost_source"] == "estimated"
    assert row["cost_usd"] == pytest.approx(0.1 * 1.25 + 0.9 * 0.125)

    # The startup backfill folds the same billing → same cache-aware cost.
    backfill_invocations_from_events(conn, PR)
    assert _cost("f_cache")["cost_usd"] == pytest.approx(0.1 * 1.25 + 0.9 * 0.125)


def test_projection_without_cache_split_keeps_flat_estimate():
    conn = get_db()
    append_event(conn, PR, "f_nocache", _ad("gpt-5-codex"))
    append_event(conn, PR, "f_nocache", _billing("gpt-5-codex", M, 0))
    assert _cost("f_nocache")["cost_usd"] == pytest.approx(1.25)
