"""Provider-agnostic pricing registry and cost resolver — the COST SSOT (Strategy B).

Pathly tracks every CLI spawn's usage with TWO independent strategy layers:

* **Strategy A — TOKEN COUNTING** (``runner/output.py::extract_tokens`` + ``_TOKEN_STRATEGIES``).
  Tokens are the universal, must-capture primitive; each adapter reports them differently
  (or not at all → local estimate). That layer answers *how many tokens*.
* **Strategy B — COST PRICING (this module).** Cost is a SEPARATE, provider-owned,
  frequently-changing concern, so it lives apart from token counting. Given (provider, model,
  tokens) it answers *how many dollars*. This is the ONE place rates live — never hard-code a
  $/token rate anywhere else; add it to ``PRICING`` here.

Keeping the two apart means a rate change touches only this table, and a new engine's token
extraction touches only ``_TOKEN_STRATEGIES`` — neither disturbs the other.

Lives in ``db/`` (not ``http_server/``) so the invocation projector
(``db/queries/invocation_projection.py``) can price a row without an upward import —
the layer rule is ``db/`` imports nothing internal. ``http_server/telemetry_registry.py``
re-exports the symbols below for backward compatibility; do not hand-edit that file's
copy of this table again.
"""

from __future__ import annotations

# Maps model-name prefixes to provider/adapter slugs.
# Shared by pricing.py and blueprints/telemetry.py (via the telemetry_registry
# re-export) — single source of truth.
_ADAPTER_PREFIXES: list[tuple[tuple[str, ...], str]] = [
    (("claude-",), "claude"),
    (("gpt-", "o1-", "o3-", "o4-"), "codex"),
    (("gemini-",), "google"),
    (("copilot-",), "copilot"),
]

# Keyed by provider slug → model-family-prefix → (input_$/MTok, output_$/MTok).
# Prefix matching: longest matching prefix wins.
PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "claude": {
        "claude-opus-4": (15.00, 75.00),
        "claude-sonnet-4": (3.00, 15.00),
        "claude-haiku-4": (0.80, 4.00),
    },
    "codex": {
        "gpt-4o": (2.50, 10.00),
        "gpt-5": (1.25, 10.00),  # codex default family; verify rate later
        "o1": (15.00, 60.00),
        "o3": (10.00, 40.00),
    },
    "google": {
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-2.5-flash": (0.075, 0.30),
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

    def all_providers(self) -> dict[str, dict[str, dict[str, float]]]:
        """Return the full pricing table for the API endpoint."""
        return {
            provider: {
                model: {"input": in_rate, "output": out_rate}
                for model, (in_rate, out_rate) in models.items()
            }
            for provider, models in PRICING.items()
        }


def infer_provider(model: str) -> str:
    """Return the provider slug for *model* via prefix match, or ``"unknown"``."""
    m = (model or "").lower()
    for prefixes, slug in _ADAPTER_PREFIXES:
        if any(m.startswith(p) for p in prefixes):
            return slug
    return "unknown"


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> tuple[float, str]:
    """Resolve (cost_usd, cost_source) for *model*, inferring its provider from the name."""
    return PricingRegistry().compute(infer_provider(model), model, tokens_in, tokens_out)


# When only an adapter slug is known (a renderer one-shot spawns with no explicit --model, so
# the CLI runs its built-in default), fall back to that adapter's representative model family so
# a token-bearing run can still be estimated. Advisory only (cost_source stays "estimated").
ADAPTER_DEFAULT_MODEL: dict[str, str] = {
    "codex": "gpt-5",
    "claude": "claude-sonnet-4",
    "agy": "gemini-2.5-pro",
    "antigravity": "gemini-2.5-pro",
    "gemini": "gemini-2.5-pro",
}


def estimate_cost_for(name: str, tokens_in: int, tokens_out: int) -> tuple[float, str]:
    """Like :func:`estimate_cost`, but *name* may be a model OR an adapter slug.

    Tries *name* as a model first; if it doesn't resolve to a priced provider, retries with the
    adapter's default model family (``ADAPTER_DEFAULT_MODEL``). Returns (0.0, "unpriced") when
    neither resolves or there are no tokens.
    """
    cost, src = estimate_cost(name, tokens_in, tokens_out)
    if src == "estimated":
        return cost, src
    fallback = ADAPTER_DEFAULT_MODEL.get((name or "").strip().lower())
    if fallback:
        return estimate_cost(fallback, tokens_in, tokens_out)
    return cost, src
