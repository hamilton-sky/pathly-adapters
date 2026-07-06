"""Goal slugs must be short + human-readable — goals/backend-api-<id>/, not
goals/<whole-48-char-title>-<id>/.

The base is the first few MEANINGFUL words of the goal title; ensure_goal_slug appends
goal_id[:8] for uniqueness. This matters most for multi-goal features, where you read
goals/backend-.../ , goals/frontend-.../ , goals/db-.../ side by side.
"""

from pathly_orchestrator.supervisor.slug import _slugify


def test_readable_base_is_first_meaningful_words():
    assert _slugify("Studio CliMonitorBar panel - A UI/UX design review") == \
        "studio-climonitorbar-panel-ui"
    assert _slugify("Backend API layer") == "backend-api-layer"


def test_stopwords_dropped():
    assert _slugify("The Frontend of the App") == "frontend-app"


def test_empty_or_symbol_is_goal():
    assert _slugify("") == "goal"
    assert _slugify("--- @@@ ---") == "goal"


def test_capped_without_midword_truncation():
    s = _slugify("comprehensive authentication authorization subsystem redesign")
    assert len(s) <= 32
    assert not s.endswith("-")            # no dangling hyphen
    assert all(part for part in s.split("-"))  # no empty (truncated) segments
