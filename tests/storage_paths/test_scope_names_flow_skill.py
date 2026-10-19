"""``scope_names``: what may join onto the packaged flows and skills folders (chief-agent 08,
round 6). ``fsm_ops._load_flow`` and ``skills/compose_resources`` read ``core/flows/<flow>.flow.yaml``
and ``core/skills/<skill>.md`` from a request string; a goal run of the ``team`` executor makes a
folder of its flow. The gate and the readers ask the same predicates.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.scope_names import (
    is_flow_name,
    is_skill_name,
    resolves_inside,
)

PACKAGED_FLOWS = [
    "team",
    "team-build",
    "goal-loop",
    "feature-consultation",
    "quick-fix",
]
PACKAGED_SKILLS = ["planning/evaluate", "team/build", "development/execute-task", "x"]
NOT_ONE_NAME = [
    "",
    " ",
    ".",
    "..",
    "...",
    "../x",
    "a/../x",
    "/abs",
    "//server/share/x",
    "a/b",
    "a\\b",
    "C:\\x",
    "C:/x",
    "x:y",
    "x\0y",
    "x/",
    None,
    7,
    ["a"],
    {"a": 1},
]


@pytest.mark.parametrize("name", PACKAGED_FLOWS + ["Q3 plan", "v1.2.3", "café"])
def test_a_flow_is_one_folder_name(name):
    assert is_flow_name(name)


@pytest.mark.parametrize("value", NOT_ONE_NAME)
def test_a_flow_that_is_not_one_name_is_refused(value):
    assert not is_flow_name(value)


@pytest.mark.parametrize("name", PACKAGED_SKILLS)
def test_a_skill_is_a_name_or_a_category_and_a_name(name):
    assert is_skill_name(name)


@pytest.mark.parametrize(
    "value",
    [v for v in NOT_ONE_NAME if v != "a/b"] + ["a//b", "a/b/", "/a/b", "a/../b"],
)
def test_a_skill_that_is_a_path_is_refused(value):
    assert not is_skill_name(value)


def test_a_path_resolves_inside_a_root_only_when_it_stays_there(tmp_path):
    root = tmp_path / "flows"
    root.mkdir()
    inside = root / "team.flow.yaml"
    outside = tmp_path / "other.flow.yaml"

    assert resolves_inside(root, inside)
    assert resolves_inside(root, root / "sub" / ".." / "x")
    assert not resolves_inside(root, outside)
    assert not resolves_inside(root, root / ".." / "other.flow.yaml")
    # joining an absolute path REPLACES the root, which is the case the check is for
    assert not resolves_inside(root, root.joinpath(str(outside)))


def test_a_link_out_of_the_root_does_not_resolve_inside(tmp_path):
    root = tmp_path / "flows"
    root.mkdir()
    target = tmp_path / "secret.yaml"
    target.write_text("x")
    link = root / "team.flow.yaml"
    link.symlink_to(target)

    assert not resolves_inside(root, link)


def test_a_resource_that_is_not_a_real_path_is_answered_by_its_name():
    """A packaged resource that is not a file on disk (a zipped wheel) has no link to follow;
    its name was checked by the name predicates."""
    assert resolves_inside(object(), object())
