"""The board-search fragment — an agent's own query back to the board.

Board context is pushed from ONE query the runner derives from the task
description. `board-search` gives the agent the second, self-authored query it
previously had no way to make: `/comms/search` existed but no fragment exposed
it, so an agent handed a weak semantic match had no recourse but to proceed.

Wired alongside `catalog-pull` — wherever an agent may already PULL from the
board by path, it may also SEARCH it by question.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.skills.compose import compose_skill

_HEADING = "## Searching the board"

# Every skill that composes catalog-pull composes board-search too.
_SEARCH_SKILLS = [
    "team/build",
    "team/review",
    "development/build",
    "development/review",
    "debug/build",
]


@pytest.mark.parametrize("skill", _SEARCH_SKILLS)
def test_search_fragment_composes_exactly_once(skill):
    out = compose_skill(skill, "claude")
    assert out.count(_HEADING) == 1, f"{skill}: board-search not composed exactly once"


@pytest.mark.parametrize("skill", _SEARCH_SKILLS)
def test_search_pairs_with_catalog_pull(skill):
    """The two pull affordances travel together — search finds it, catalog reads it."""
    out = compose_skill(skill, "claude")
    assert "## Pulling context from the Board Catalog" in out
    assert _HEADING in out


def test_not_composed_into_unrelated_skills():
    """Scope stays where catalog-pull already reaches; design/retro are untouched."""
    for skill in ("team/design", "team/retro"):
        assert _HEADING not in compose_skill(skill, "claude")


def test_fragment_targets_the_real_search_endpoint():
    out = compose_skill("team/build", "claude")
    body = out[out.index(_HEADING) :]
    assert "/comms/search" in body
    # The hardened bounds the route enforces must not be misdescribed to the agent.
    assert "512" in body, "query length cap should be stated"
    assert "max 50" in body, "k cap should be stated"


def test_fragment_only_uses_substituted_placeholders():
    """`<feature>`/`<board>` are injected by the runner; anything else ships literally."""
    from tests._paths import SRC

    text = (SRC / "pathly_data/core/skills/fragments/board-search.md").read_text(
        encoding="utf-8"
    )
    import re

    used = set(re.findall(r"<([a-z_]+)>", text))
    substituted = {"feature", "board", "project_root", "agent", "run_id"}
    assert used <= substituted, f"unsubstituted placeholder(s): {used - substituted}"


def test_empty_result_is_documented_as_an_answer():
    """`[]` is a real 'nothing here', not a failure — the agent must not loop on it."""
    body = compose_skill("team/build", "claude")
    body = body[body.index(_HEADING) :]
    assert "never padded" in body
