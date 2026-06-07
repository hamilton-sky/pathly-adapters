"""Pricing table and cost computation helpers."""
from __future__ import annotations

MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4":    (15.00, 75.00),
    "claude-sonnet-4":  ( 3.00, 15.00),
    "claude-haiku-4":   ( 0.80,  4.00),
}


def compute_cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    """Compute cost_usd from model name and token counts.

    Returns 0.0 if the model is not in the pricing table.
    """
    in_rate, out_rate = next(
        (v for k, v in MODEL_PRICING.items() if model.startswith(k)),
        (0.0, 0.0),
    )
    if in_rate <= 0:
        return 0.0
    return round(
        (tokens_in / 1_000_000 * in_rate) + (tokens_out / 1_000_000 * out_rate), 6
    )
