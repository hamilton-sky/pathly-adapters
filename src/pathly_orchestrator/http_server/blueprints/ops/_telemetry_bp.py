"""Shared Blueprint, constants, and helpers for telemetry routes."""

from __future__ import annotations

import logging

from flask import Blueprint

from pathly_orchestrator import eventlog  # noqa: F401
from pathly_orchestrator.db import append_event as _db_append_event  # noqa: F401
from pathly_orchestrator.db.connection import get_db as _get_db  # noqa: F401
from pathly_orchestrator.feature_flags import flags  # noqa: F401
from pathly_telemetry.storage import append_activity  # noqa: F401
from ...telemetry_registry import PricingRegistry, _ADAPTER_PREFIXES  # noqa: F401

bp = Blueprint("telemetry", __name__)

_VALID_PHASES = {
    "analyze",
    "build",
    "design",
    "implement",
    "plan",
    "review",
    "scout",
    "storm",
    "test",
}
_VALID_EVENT_TYPES = {"PHASE_START", "PHASE_DONE"}

logger = logging.getLogger("pathly.http")


def _infer_adapter(model: str) -> str:
    """Return a CLI/adapter name inferred from the model-name prefix."""
    m = model.lower()
    for prefixes, name in _ADAPTER_PREFIXES:
        if any(m.startswith(p) for p in prefixes):
            return name
    return "unknown" if model else ""
