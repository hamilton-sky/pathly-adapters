import logging
import os

logger = logging.getLogger("pathly.storage")


def _is_unsafe_topic(topic: str):
    """Return a reason string if topic is unsafe for use as a filesystem slug, else None."""
    if not topic or not topic.strip():
        return "empty"
    if os.path.isabs(topic) or topic.startswith("/"):
        return "absolute path"
    # Check backslash and colon ONLY — do NOT flag bare forward-slash (covered by isabs above;
    # flagging it would false-positive a working POSIX sub-path and break P0 behavior-neutrality)
    if any(c in topic for c in ("\\", ":")):
        return "contains path separator"
    # Split on both separators to catch traversal segments
    parts = topic.replace("\\", "/").split("/")
    if ".." in parts:
        return "contains traversal segment"
    return None


def _safe_topic(topic: str) -> str:
    """P1: RAISE ValueError for unsafe topics (was WARN in P0)."""
    reason = _is_unsafe_topic(topic)
    if reason:
        raise ValueError(
            f"unsafe topic {topic!r} ({reason}); slug/scope split requires a filesystem-safe slug"
        )
    return topic
