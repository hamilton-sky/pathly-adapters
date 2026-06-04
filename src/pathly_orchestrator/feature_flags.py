"""Simple environment-variable-based feature flags.

Usage:
    from pathly_orchestrator.feature_flags import flags

    if flags.feedback_watcher:
        ...
"""

from __future__ import annotations

import os


def _bool(key: str, default: bool = True) -> bool:
    val = os.environ.get(key, "").lower()
    if val in ("1", "true", "yes", "on"):
        return True
    if val in ("0", "false", "no", "off"):
        return False
    return default


class FeatureFlags:
    """Feature flags read from environment variables at access time."""

    @property
    def feedback_watcher(self) -> bool:
        """Enable the background feedback file watcher."""
        return _bool("PATHLY_FF_FEEDBACK_WATCHER", True)

    @property
    def sse_streaming(self) -> bool:
        """Enable the SSE event stream endpoint."""
        return _bool("PATHLY_FF_SSE_STREAMING", True)

    @property
    def telemetry(self) -> bool:
        """Enable activity telemetry recording."""
        return _bool("PATHLY_FF_TELEMETRY", True)

    @property
    def rate_limiting(self) -> bool:
        """Enable per-IP rate limiting on HTTP endpoints."""
        return _bool("PATHLY_FF_RATE_LIMITING", True)

    @property
    def early_advance(self) -> bool:
        return _bool("PATHLY_RUNNER_EARLY_ADVANCE", True)

    @property
    def interactive(self) -> bool:
        return _bool("PATHLY_RUNNER_INTERACTIVE", True)


flags = FeatureFlags()
