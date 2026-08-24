"""Prompt-cache token capture and tiered pricing.

Pins the fix for the bug where cache reads/writes were folded into a single ``tokens_in``
lump and priced at the full input rate. ``tokens_in`` keeps its cache-INCLUSIVE meaning;
the split is carried alongside it and carved out at pricing time.

Every assertion here is an invariant that a future edit could plausibly break:

* the lump/split relationship (the split is a SUBSET of ``tokens_in``, never an addend)
* backwards compatibility (no split supplied == the old lump-at-1x behaviour, exactly)
* the clamp (a malformed split must not drive uncached negative and refund the bill)
* the multiplier constants, including WHY the write tier is 2.0x and not the
  published-headline 1.25x -- see ``test_cache_write_multiplier_is_the_1h_tier``
"""

import pytest

from pathly_orchestrator.db.pricing import (
    CACHE_READ_MULTIPLIER,
    CACHE_WRITE_MULTIPLIER,
    PricingRegistry,
    estimate_cost,
    estimate_cost_for,
)
from pathly_orchestrator.runner.output import extract_cache_tokens, parse_result

# claude-sonnet-4 => (3.00 input, 15.00 output) $/MTok. Chosen because the rates are round
# numbers, so the expected costs below are readable arithmetic rather than magic constants.
MODEL = "claude-sonnet-4-6"
IN_RATE = 3.00


@pytest.fixture
def registry():
    return PricingRegistry()


# --------------------------------------------------------------------------------------
# Producer: extract_cache_tokens
# --------------------------------------------------------------------------------------


def test_extracts_split_from_top_level_usage():
    payload = {
        "usage": {
            "input_tokens": 1_000,
            "cache_read_input_tokens": 95_000,
            "cache_creation_input_tokens": 4_000,
            "output_tokens": 500,
        }
    }
    assert extract_cache_tokens(payload) == (95_000, 4_000)


def test_extracts_split_from_camel_case_usage():
    payload = {
        "usage": {
            "inputTokens": 1_000,
            "cacheReadInputTokens": 95_000,
            "cacheCreationInputTokens": 4_000,
        }
    }
    assert extract_cache_tokens(payload) == (95_000, 4_000)


def test_falls_back_to_model_usage_and_sums_across_models():
    """A truncated envelope can lose the top-level ``usage`` block but keep ``modelUsage``."""
    payload = {
        "modelUsage": {
            "claude-sonnet-4-6": {
                "cacheReadInputTokens": 60_000,
                "cacheCreationInputTokens": 1_000,
            },
            "claude-haiku-4-5": {
                "cacheReadInputTokens": 35_000,
                "cacheCreationInputTokens": 3_000,
            },
        }
    }
    assert extract_cache_tokens(payload) == (95_000, 4_000)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"usage": None},
        {"usage": {"cache_read_input_tokens": "not-a-number"}},
        {"modelUsage": ["not", "a", "dict"]},
        {"modelUsage": {"m": "not-a-dict"}},
    ],
)
def test_malformed_payloads_yield_zero_and_never_raise(payload):
    assert extract_cache_tokens(payload) == (0, 0)


def test_parse_result_surfaces_the_split_alongside_the_lump():
    raw = (
        '{"type":"result","total_cost_usd":0.42,"usage":'
        '{"input_tokens":1000,"cache_read_input_tokens":95000,'
        '"cache_creation_input_tokens":4000,"output_tokens":500}}'
    )
    parsed = parse_result("claude", raw)
    assert parsed["cache_read_tokens"] == 95_000
    assert parsed["cache_write_tokens"] == 4_000
    # The lump stays cache-INCLUSIVE: 1000 uncached + 95000 read + 4000 write.
    assert parsed["tokens_in"] == 100_000


# --------------------------------------------------------------------------------------
# Pricing: the tiering itself
# --------------------------------------------------------------------------------------


def test_omitting_the_split_reproduces_the_old_lump_behaviour_exactly(registry):
    """Backwards compatibility. Every pre-fix caller passes 4 args and must not shift."""
    lump_only = registry.compute("claude", MODEL, 1_000_000, 0)
    explicit_zero = registry.compute("claude", MODEL, 1_000_000, 0, 0, 0)
    assert lump_only == explicit_zero
    assert lump_only == (pytest.approx(1_000_000 / 1e6 * IN_RATE), "estimated")


def test_split_is_carved_out_of_the_lump_not_added_to_it(registry):
    """95% read / 2% write / 3% uncached -- the shape of a real agent run."""
    cost, source = registry.compute(
        "claude", MODEL, tokens_in=1_000_000, tokens_out=0,
        cache_read_tokens=950_000, cache_write_tokens=20_000,
    )
    expected = (
        30_000 / 1e6 * IN_RATE                            # uncached at 1x
        + 950_000 / 1e6 * IN_RATE * CACHE_READ_MULTIPLIER  # reads at 0.1x
        + 20_000 / 1e6 * IN_RATE * CACHE_WRITE_MULTIPLIER  # writes at 2.0x
    )
    assert source == "estimated"
    assert cost == pytest.approx(expected)
    assert cost == pytest.approx(0.495)


def test_cache_heavy_run_prices_below_the_lump(registry):
    """The whole point: billing a cache-heavy run as pure input overstates it severalfold."""
    lump, _ = registry.compute("claude", MODEL, 1_000_000, 0)
    tiered, _ = registry.compute("claude", MODEL, 1_000_000, 0, 950_000, 20_000)
    assert tiered < lump
    assert lump / tiered > 3


def test_split_exceeding_the_lump_is_clamped_and_never_refunds(registry):
    """A malformed pair must not drive uncached negative -- cost stays >= 0 and <= the lump."""
    cost, source = registry.compute(
        "claude", MODEL, tokens_in=100, tokens_out=0,
        cache_read_tokens=900_000, cache_write_tokens=900_000,
    )
    lump, _ = registry.compute("claude", MODEL, 100, 0)
    assert source == "estimated"
    assert cost >= 0
    assert cost <= lump


def test_negative_split_values_are_floored_at_zero(registry):
    cost, _ = registry.compute("claude", MODEL, 1_000_000, 0, -5_000, -5_000)
    lump, _ = registry.compute("claude", MODEL, 1_000_000, 0)
    assert cost == pytest.approx(lump)


def test_cache_write_multiplier_is_the_1h_tier():
    """2.0x (1-hour) is measured, not assumed -- do NOT "correct" this to the 1.25x headline.

    Against a real 3,683-line Claude Code session log (2026-08-24), every one of 1,772 turns
    carried ``usage.cache_creation``, and the TTL split was 3,713,390 tokens of
    ``ephemeral_1h_input_tokens`` against ZERO ``ephemeral_5m_input_tokens``. Pricing agent
    runs at the 5m rate understates the cache-write line by 37.5%.
    """
    assert CACHE_WRITE_MULTIPLIER == 2.0
    assert CACHE_READ_MULTIPLIER == 0.1


def test_unknown_model_stays_unpriced_even_with_a_cache_split(registry):
    assert registry.compute("claude", "claude-nonexistent-9", 1_000, 500, 900, 100) == (
        0.0,
        "unpriced",
    )
    assert registry.compute("nope", MODEL, 1_000, 500, 900, 100) == (0.0, "unpriced")


def test_zero_tokens_stays_unpriced_even_with_a_cache_split(registry):
    assert registry.compute("claude", MODEL, 0, 0, 500, 500) == (0.0, "unpriced")


def test_estimate_cost_threads_the_split_through_provider_inference():
    tiered, source = estimate_cost(MODEL, 1_000_000, 0, 950_000, 20_000)
    assert source == "estimated"
    assert tiered == pytest.approx(0.495)


def test_estimate_cost_for_keeps_its_three_arg_signature():
    """Legacy callers (renderer one-shots) pass an adapter slug and no cache split."""
    cost, source = estimate_cost_for("codex", 100_000, 20_000)
    assert source == "estimated"
    assert cost > 0


def test_pricing_endpoint_exposes_the_cache_tiers(registry):
    """/telemetry/pricing must not imply a 2-bucket world."""
    entry = registry.all_providers()["claude"]["claude-sonnet-4"]
    assert entry["cache_read"] == pytest.approx(entry["input"] * CACHE_READ_MULTIPLIER)
    assert entry["cache_write"] == pytest.approx(entry["input"] * CACHE_WRITE_MULTIPLIER)


# --------------------------------------------------------------------------------------
# Projection chokepoint: _price_if_needed
# --------------------------------------------------------------------------------------


def test_projection_prices_a_zero_cost_row_with_its_cache_split():
    from pathly_orchestrator.db.queries.invocation_projection import _price_if_needed

    cost, source = _price_if_needed(0.0, "unpriced", MODEL, 1_000_000, 0, 950_000, 20_000)
    assert source == "estimated"
    assert cost == pytest.approx(0.495)


def test_projection_never_repriced_a_row_that_already_has_a_cost():
    """Idempotent: a provider-reported cost is authoritative and must survive re-projection."""
    from pathly_orchestrator.db.queries.invocation_projection import _price_if_needed

    assert _price_if_needed(8.29, "reported", MODEL, 1_000_000, 0, 950_000, 20_000) == (
        8.29,
        "reported",
    )


# --------------------------------------------------------------------------------------
# Historical rows: watermark, not backfill
# --------------------------------------------------------------------------------------


def test_cache_split_watermark_is_stamped_once_and_is_stable(tmp_path):
    """Rows before this timestamp read 0 because nothing captured the split, not because no
    cache was used. Reconstructing them would mean re-parsing stdout that was often truncated
    in the first place, so we record where the data starts instead of inventing it."""
    import sqlite3

    from pathly_orchestrator.db.migrations_incremental import (
        _stamp_cache_split_watermark,
    )

    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    # Mirrors the real schema — value/updated_at are NOT NULL, and an INSERT that omits
    # updated_at raises into the swallowing except (which is how the first version of this
    # watermark silently did nothing).
    conn.execute(
        "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL, "
        "updated_at TEXT NOT NULL)"
    )

    _stamp_cache_split_watermark(conn)
    first = conn.execute(
        "SELECT value FROM app_settings WHERE key='telemetry.cache_split_since'"
    ).fetchone()["value"]
    assert first

    _stamp_cache_split_watermark(conn)  # a later server start must not move it
    second = conn.execute(
        "SELECT value FROM app_settings WHERE key='telemetry.cache_split_since'"
    ).fetchone()["value"]
    assert second == first
    conn.close()


def test_cache_split_watermark_never_blocks_startup(tmp_path):
    """No app_settings table at all — a telemetry watermark must not raise into migrations."""
    import sqlite3

    from pathly_orchestrator.db.migrations_incremental import (
        _stamp_cache_split_watermark,
    )

    conn = sqlite3.connect(tmp_path / "empty.db")
    _stamp_cache_split_watermark(conn)  # must not raise
    conn.close()


def test_trends_endpoint_reports_the_watermark():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        body = c.get("/telemetry/trends?feature=").get_json()
    assert "cache_split_since" in body, (
        "a consumer cannot tell 'no cache used' from 'split not captured' without it"
    )
