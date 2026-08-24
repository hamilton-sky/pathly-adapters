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

# Prompt-cache tiers, expressed as multipliers on the model's INPUT rate rather than as
# per-model absolute rates — every provider that offers prompt caching prices it that way, so
# one pair of constants covers the whole table and cannot drift row by row.
#   read  0.1x  — Anthropic cache-read and OpenAI cached-input both bill at 1/10 of input.
#   write 2.0x  — Anthropic ephemeral cache creation, 1-HOUR tier.
#
# On the write multiplier: this was originally 1.25x (the 5-minute tier), on the assumption that
# 5m is Claude Code's default and that the envelope does not break creation out by TTL. Both
# halves of that assumption are wrong, measured against a real 3,683-line session log on
# 2026-08-24: `usage.cache_creation.{ephemeral_5m_input_tokens, ephemeral_1h_input_tokens}` is
# present on 100% of turns (1,772/1,772), and the split was 3,713,390 tokens of 1h against
# ZERO of 5m. Pricing agent runs at 1.25x understates the cache-write line by 37.5%.
#
# 2.0x is therefore an evidence-based default, not a conservative guess.
#
# We deliberately do NOT split the two tiers through the pipeline yet: that needs a third token
# column plus a migration, and the measured 5m share is 0%, so the accuracy gain today is nil.
# `CACHE_WRITE_5M_MULTIPLIER` is recorded for the day a workload actually uses the 5m tier — at
# which point `extract_cache_tokens` should return the split and `compute()` should price each
# tier separately. Until then one blended rate at the observed tier is the honest simplification.
CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 2.0
CACHE_WRITE_5M_MULTIPLIER = 1.25  # unused today; see note above

# Keyed by provider slug → model-family-prefix → (input_$/MTok, output_$/MTok).
# Prefix matching: longest matching prefix wins.
#
# Rates verified 2026-07-15 against the providers' own pricing:
#   - Anthropic: the claude-api skill model table (platform.claude.com/docs/.../pricing).
#   - OpenAI:    developers.openai.com/api/docs/pricing.
#   - Google:    ai.google.dev/gemini-api/docs/pricing.
# Longest-prefix wins, so a specific model (e.g. "claude-opus-4-1") overrides its family default.
PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "claude": {
        "claude-fable-5": (10.00, 50.00),
        # Opus 4.5+ is $5/$25; only legacy 4.0/4.1 were $15/$75 (kept via the longer prefixes).
        "claude-opus-4": (5.00, 25.00),
        "claude-opus-4-0": (15.00, 75.00),
        "claude-opus-4-1": (15.00, 75.00),
        "claude-sonnet-5": (3.00, 15.00),  # $2/$10 intro through 2026-08-31
        "claude-sonnet-4": (3.00, 15.00),  # Sonnet 4.5 / 4.6
        "claude-haiku-4": (1.00, 5.00),  # Haiku 4.5
    },
    # gpt-* → codex provider (see _ADAPTER_PREFIXES). codex spawns with no explicit --model, so the
    # user's codex 0.142 runs report `gpt-5` / `gpt-5-codex` → priced via the "gpt-5" prefix.
    "codex": {
        "gpt-5": (1.25, 10.00),  # base GPT-5 / gpt-5-codex (launch rate)
        "gpt-5.3-codex": (1.75, 14.00),
        "gpt-5.4": (2.50, 15.00),
        "gpt-5.5": (5.00, 30.00),
        "gpt-5.6-sol": (5.00, 30.00),
        "gpt-5.6-terra": (2.50, 15.00),
        "gpt-5.6-luna": (1.00, 6.00),
        "gpt-4o": (2.50, 10.00),
        "o1": (15.00, 60.00),
        "o3": (10.00, 40.00),
    },
    # Gemini 2.5 Pro is context-tiered (≤200k / >200k); we price the ≤200k rate (the common case;
    # >200k is (2.50, 15.00)). agy / antigravity default to gemini-2.5-pro.
    "google": {
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-2.5-flash-lite": (0.10, 0.40),
        "gemini-2.5-flash": (0.30, 2.50),
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
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0,
    ) -> tuple[float, str]:
        """Return (cost_usd, cost_source).

        Prefix-matches model against the provider's table; longest key wins.
        Returns (0.0, "unpriced") when provider is unknown or no prefix matches,
        or when both token counts are zero.

        ``tokens_in`` is cache-INCLUSIVE (see runner/output.py::extract_cache_tokens).
        When a cache split is supplied it is carved OUT of the lump and re-priced at its
        own tier — cache reads at 0.1x input, cache writes at 1.25x input — leaving only
        genuinely uncached input at 1x. Billing the whole lump at 1x overstates a
        cache-heavy agent run by roughly 3x. Omitting the split preserves the old
        (lump-at-1x) behaviour exactly, so existing callers are unaffected.
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
        c_read = max(0, int(cache_read_tokens or 0))
        c_write = max(0, int(cache_write_tokens or 0))
        # Clamp: the split is a SUBSET of the lump. A malformed pair that exceeds tokens_in
        # must not drive uncached negative and refund the bill.
        if c_read + c_write > tokens_in:
            c_read = min(c_read, tokens_in)
            c_write = max(0, tokens_in - c_read)
        uncached_in = tokens_in - c_read - c_write
        cost = round(
            (uncached_in / 1_000_000 * in_rate)
            + (c_read / 1_000_000 * in_rate * CACHE_READ_MULTIPLIER)
            + (c_write / 1_000_000 * in_rate * CACHE_WRITE_MULTIPLIER)
            + (tokens_out / 1_000_000 * out_rate),
            6,
        )
        return (cost, "estimated")

    def all_providers(self) -> dict[str, dict[str, dict[str, float]]]:
        """Return the full pricing table for the API endpoint."""
        return {
            provider: {
                model: {
                    "input": in_rate,
                    "output": out_rate,
                    # Surfaced so the endpoint stops implying a 2-bucket world. A reader
                    # that sees only input/output cannot tell a cache-tiered estimate from
                    # a lump one.
                    "cache_read": round(in_rate * CACHE_READ_MULTIPLIER, 6),
                    "cache_write": round(in_rate * CACHE_WRITE_MULTIPLIER, 6),
                }
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


def estimate_cost(
    model: str,
    tokens_in: int,
    tokens_out: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> tuple[float, str]:
    """Resolve (cost_usd, cost_source) for *model*, inferring its provider from the name.

    The optional cache split is carved out of the cache-inclusive ``tokens_in`` and priced
    at its own tier; see :meth:`PricingRegistry.compute`.
    """
    return PricingRegistry().compute(
        infer_provider(model),
        model,
        tokens_in,
        tokens_out,
        cache_read_tokens,
        cache_write_tokens,
    )


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
