"""Pathly hooks for feedback classification and TTL injection."""

FEEDBACK_PROTOCOL_VERSION = "1.0"

from . import classify_feedback, inject_feedback_ttl  # noqa: F401
