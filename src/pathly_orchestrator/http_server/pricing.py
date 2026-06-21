"""Pricing table and cost computation helpers."""

from __future__ import annotations

from pathly_orchestrator.http_server.telemetry_registry import (
    PricingRegistry,
    _ADAPTER_PREFIXES,
)

# Legacy per-model pricing table — kept as reference only; no longer used at runtime.
# MODEL_PRICING: dict[str, tuple[float, float]] = {
#     "claude-opus-4":    (15.00, 75.00),
#     "claude-sonnet-4":  ( 3.00, 15.00),
#     "claude-haiku-4":   ( 0.80,  4.00),
# }


def _infer_provider(model: str) -> str:
    m = model.lower()
    for prefixes, slug in _ADAPTER_PREFIXES:
        if any(m.startswith(p) for p in prefixes):
            return slug
    return "unknown"


def compute_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Compute cost_usd by delegating to PricingRegistry.

    Returns 0.0 if the model cannot be priced.
    """
    provider = _infer_provider(model)
    cost_usd, _ = PricingRegistry().compute(provider, model, tokens_in, tokens_out)
    return cost_usd
