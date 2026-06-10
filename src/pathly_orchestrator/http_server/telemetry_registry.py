"""Provider-agnostic pricing registry and cost resolver."""
from __future__ import annotations

# Keyed by provider slug → model-family-prefix → (input_$/MTok, output_$/MTok).
# Prefix matching: longest matching prefix wins.
PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "claude": {
        "claude-opus-4":   (15.00, 75.00),
        "claude-sonnet-4": ( 3.00, 15.00),
        "claude-haiku-4":  ( 0.80,  4.00),
    },
    "codex": {
        "gpt-4o": ( 2.50, 10.00),
        "o1":     (15.00, 60.00),
        "o3":     (10.00, 40.00),
    },
    "google": {
        "gemini-2.5-pro":   ( 1.25, 10.00),
        "gemini-2.5-flash": ( 0.075, 0.30),
    },
    "antigravity": {
        "gemini-2.5-pro": (1.25, 10.00),
    },
}


class PricingRegistry:
    """Resolve cost_usd and cost_source for any provider/model combination."""

    def compute(
        self,
        provider: str,
        model: str,
        tokens_in: int,
        tokens_out: int,
    ) -> tuple[float, str]:
        """Return (cost_usd, cost_source).

        Prefix-matches model against the provider's table; longest key wins.
        Returns (0.0, "unpriced") when provider is unknown or no prefix matches,
        or when both token counts are zero.
        """
        if tokens_in == 0 and tokens_out == 0:
            return (0.0, "unpriced")

        table = PRICING.get(provider, {})
        if not table:
            return (0.0, "unpriced")

        # Find the longest matching prefix key.
        best_key: str | None = None
        for key in table:
            if model.startswith(key):
                if best_key is None or len(key) > len(best_key):
                    best_key = key

        if best_key is None:
            return (0.0, "unpriced")

        in_rate, out_rate = table[best_key]
        cost = round(
            (tokens_in / 1_000_000 * in_rate) + (tokens_out / 1_000_000 * out_rate),
            6,
        )
        return (cost, "estimated")

    def all_providers(self) -> dict[str, dict[str, tuple[float, float]]]:
        """Return the full pricing table for the API endpoint."""
        return {
            provider: dict(models)
            for provider, models in PRICING.items()
        }
