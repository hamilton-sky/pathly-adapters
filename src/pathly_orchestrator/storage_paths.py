import logging
import os

logger = logging.getLogger("pathly.storage")

# Direct children of pathly/ that are containers, not features — a topic may not use
# one of these as its first path segment or it would collide with a structural dir.
_RESERVED_TOPICS = frozenset(
    {
        "features",
        "project",
        "plans",
        "debugs",
        "explorations",
        "fixes",
        "goals",
        "lessons",
        "board-artifacts",
        "pipeline-walkthrough",
        ".archive",
    }
)


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
    # Reject only a BARE single-segment topic equal to a structural dir (a feature named
    # "goals"/"plans"/…). A multi-segment address like "goals/<slug>" is an explicit
    # nested path the caller chose on purpose — leave it alone.
    if len(parts) == 1 and parts[0] in _RESERVED_TOPICS:
        return f"reserved name {parts[0]!r} (collides with a pathly/ structural dir)"
    return None


def _safe_topic(topic: str) -> str:
    """P1: RAISE ValueError for unsafe topics (was WARN in P0)."""
    reason = _is_unsafe_topic(topic)
    if reason:
        raise ValueError(
            f"unsafe topic {topic!r} ({reason}); slug/scope split requires a filesystem-safe slug"
        )
    return topic
