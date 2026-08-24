"""Cost-pricing chokepoint for projected invocation rows.

Split out of ``invocation_projection.py`` so that file stays within the 400-line SOLID
ratchet: the projector owns "one row per AGENT_DONE, billing folded in", and pricing —
deciding whether a row needs a cost estimate and at what cache tier — is a separate
concern that changes for different reasons (a provider rate change, a new cache tier).

Every projected row passes through :func:`price_if_needed` exactly once.
"""

from __future__ import annotations


def num(v: object) -> float:
    """Coerce a token/cost field to float, treating None/blank/garbage as 0."""
    try:
        return float(v or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def price_if_needed(
    cost: float,
    cost_source: str,
    model: str | None,
    tokens_in: object,
    tokens_out: object,
    cache_read: object = 0,
    cache_write: object = 0,
) -> tuple[float, str]:
    """Estimate cost from tokens when the event stream reported none.

    Idempotent chokepoint: only fires when ``cost`` is exactly 0 (a priced cost —
    provider-reported OR an earlier estimate — is never re-priced/overwritten).
    agy/gemini rows with tokens still 0 are marked 'unavailable' rather than left
    'unpriced' — agy emits no usage telemetry at all, so there is nothing to estimate.
    """
    if cost and cost > 0:
        return cost, cost_source
    tin, tout = int(num(tokens_in)), int(num(tokens_out))
    if tin + tout > 0:
        from ..pricing import estimate_cost  # intra-db import, layer-safe

        # tokens_in is cache-INCLUSIVE. Passing the lump alone bills cache reads (0.1x) and
        # cache writes (2.0x) at the full input rate, which on a cache-heavy agent run
        # overstates cost by ~3x. Hand the split through so estimate_cost can tier it.
        est, src = estimate_cost(
            model or "", tin, tout, int(num(cache_read)), int(num(cache_write))
        )
        if src == "estimated":
            return est, "estimated"
        return cost, cost_source
    m = (model or "").lower()
    if m.startswith("gemini-") or m in ("antigravity", "agy"):
        return cost, "unavailable"
    # A codex/openai stage bills LATE via the spawn-gate BILLING_UPDATE — its AGENT_DONE
    # self-reports 0 tokens, so a 0-token/0-cost row here is AWAITING that reconciliation,
    # not genuinely free. Mark it 'pending' (not a misleading 'unpriced $0'); when the
    # BILLING_UPDATE folds in the real tokens this re-prices to 'estimated'.
    if m.startswith(("gpt-", "gpt5", "o1", "o3", "o4")) or "codex" in m:
        return cost, "pending"
    return cost, cost_source
