import pytest
from pathly_orchestrator.storage_paths import _is_unsafe_topic, _safe_topic


def test_normal_slug_passes_through():
    assert _safe_topic("my-feature-123") == "my-feature-123"
    assert _is_unsafe_topic("my-feature-123") is None


def test_goal_id_slug_passes():
    assert _is_unsafe_topic("goal-abc12345") is None


def test_absolute_forward_slash_raises():
    topic = "/absolute/path/to/something"
    with pytest.raises(ValueError, match="unsafe topic"):
        _safe_topic(topic)


def test_absolute_backslash_path_raises():
    topic = "C:\\Users\\Yafit\\pathly-adapters"
    with pytest.raises(ValueError, match="unsafe topic"):
        _safe_topic(topic)


def test_traversal_segment_detected():
    assert _is_unsafe_topic("../escape") is not None
    assert _is_unsafe_topic("a/../b") is not None


def test_empty_string_detected():
    assert _is_unsafe_topic("") is not None


def test_whitespace_only_detected():
    assert _is_unsafe_topic("   ") is not None


def test_forward_slash_alone_is_absolute():
    # A bare "/" is absolute (os.path.isabs returns True), so it IS flagged
    assert _is_unsafe_topic("/") is not None


def test_subpath_with_forward_slash_not_flagged():
    # A relative sub-path like "goals/my-slug" must NOT be flagged — it's not absolute
    assert _is_unsafe_topic("goals/my-slug") is None
