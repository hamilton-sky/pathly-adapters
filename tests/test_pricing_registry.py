"""Unit tests for PricingRegistry.compute()."""
import pytest
from pathly_orchestrator.http_server.telemetry_registry import PricingRegistry


@pytest.fixture
def registry():
    return PricingRegistry()


def test_codex_gpt4o_estimated(registry):
    cost, source = registry.compute("codex", "gpt-4o", tokens_in=100_000, tokens_out=20_000)
    assert source == "estimated"
    assert cost > 0


def test_google_gemini_25_pro_estimated(registry):
    cost, source = registry.compute("google", "gemini-2.5-pro", tokens_in=100_000, tokens_out=20_000)
    assert source == "estimated"
    assert cost > 0


def test_unknown_provider_unpriced(registry):
    cost, source = registry.compute("unknown-provider", "some-model", tokens_in=1000, tokens_out=500)
    assert source == "unpriced"
    assert cost == 0.0


def test_known_provider_unknown_model_unpriced(registry):
    cost, source = registry.compute("codex", "nonexistent-model-xyz", tokens_in=1000, tokens_out=500)
    assert source == "unpriced"
    assert cost == 0.0


def test_zero_tokens_unpriced(registry):
    cost, source = registry.compute("codex", "gpt-4o", tokens_in=0, tokens_out=0)
    assert source == "unpriced"
    assert cost == 0.0


def test_cost_calculation_accuracy(registry):
    # gpt-4o: input=$2.50/MTok, output=$10.00/MTok
    # 1M in + 1M out = $2.50 + $10.00 = $12.50
    cost, source = registry.compute("codex", "gpt-4o", tokens_in=1_000_000, tokens_out=1_000_000)
    assert source == "estimated"
    assert abs(cost - 12.50) < 1e-5


def test_gemini_flash_prefix_match(registry):
    cost, source = registry.compute("google", "gemini-2.5-flash", tokens_in=100_000, tokens_out=20_000)
    assert source == "estimated"
    assert cost > 0


def test_claude_sonnet_estimated(registry):
    cost, source = registry.compute("claude", "claude-sonnet-4-6", tokens_in=50_000, tokens_out=10_000)
    assert source == "estimated"
    assert cost > 0
