"""The ```check examples the planner is taught still parse.

`planning/plan` and the `task-dag-post` fragment each show a ```check block, and the supervisor
reads the planner's task text with `proof.checks.checks_in`. A later wording change to either
text must not break that grammar unnoticed.
"""

from __future__ import annotations

import json
import re

import pytest

from pathly_orchestrator.compose import _read_fragment, compose_skill
from pathly_orchestrator.proof.checks import Check, checks_in
from pathly_orchestrator.skills.compose import build_adapter_caps

pytestmark = pytest.mark.no_pathly_autouse

# The rules the planner is told for a command; its own examples must follow them.
_SHELL_FEATURES = ("&&", "||", "|", ";", ">", "<")


def _fragment() -> str:
    return _read_fragment("fragments", "task-dag-post")


def _assert_example(checks: list[Check]) -> None:
    assert len(checks) >= 1
    for check in checks:
        assert check.command.strip()
        assert not any(token in check.command for token in _SHELL_FEATURES), check


def test_plan_skill_example_parses_into_a_check():
    _assert_example(checks_in(compose_skill("planning/plan", "claude")))


def test_task_dag_post_fragment_example_parses_into_a_check():
    _assert_example(checks_in(_fragment()))


def test_fragment_json_example_decodes_to_the_same_block():
    """The curl body holds the block as one JSON string: decoded, it is the block shown above it."""
    match = re.search(r'^"text": (".*")$', _fragment(), re.MULTILINE)
    assert match, "the fragment shows no JSON-escaped text example"
    decoded = json.loads(match.group(1))
    assert checks_in(decoded) == checks_in(_fragment())


def test_composed_plan_prompt_with_a_goal_parses_as_a_whole():
    """With a goal the fragment is composed in: both examples read, no fence left open."""
    prompt = compose_skill("planning/plan", build_adapter_caps("claude", goal_id="g1"))
    assert "## Posting the task DAG to the Comms Board" in prompt
    in_skill = checks_in(compose_skill("planning/plan", "claude"))
    in_fragment = checks_in(_fragment())
    assert len(checks_in(prompt)) >= len(in_skill) + len(in_fragment)
