"""Pricing registry — re-exported from db/pricing (the layer-safe home)."""

from __future__ import annotations

from pathly_orchestrator.db.pricing import (
    PRICING,
    PricingRegistry,
    _ADAPTER_PREFIXES,
    estimate_cost,
    infer_provider,
)

# Explicit re-export (backward-compat shim): pins these as this module's public API so
# static analysers don't flag the imports as unused.
__all__ = [
    "PRICING",
    "PricingRegistry",
    "_ADAPTER_PREFIXES",
    "estimate_cost",
    "infer_provider",
]
