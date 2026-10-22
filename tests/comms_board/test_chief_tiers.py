"""chief-agent 04: the chief tiers and the preset-to-tier resolution.

``supervisor/chief_tiers.py`` is the one place that says what a chief may do. The action lists
are code. A preset only names a tier (front matter ``tier:`` of a ``chief/<preset>`` prompt
file); an unknown or missing tier, an unknown preset or a malformed preset name is ``status``
(read-only), so editing a preset's text can never grant power.

The tier is read from exactly the block ``strip_front_matter`` removes, so the text a chief is
given and the text its tier was read from cannot disagree (``test_the_tier_is_read_from_...``). A
front matter that is not closed by a line of ``---`` and a ``\\n``, such as one with CRLF line ends,
is not removed and names no tier. A quoted value (``tier: "operator"``) is read with its quotes, is
not a tier, and is ``status``.

The autouse conftest fixture patches ``Path.home()``, so a ``global`` prompt lands in a temp dir.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.skills.prompt_files import write_prompt_file
from pathly_orchestrator.supervisor.chief_tiers import (
    ACTIONS,
    TIERS,
    _front_matter_tier,
    actions_for,
    normalise_tier,
    resolve_preset_tier,
    strip_front_matter,
)

ALL = frozenset({"read", "post", "plan", "decide", "run", "stop", "answer"})


@pytest.fixture()
def proj(tmp_path):
    return str(tmp_path / "proj")


def _preset(proj, name, body, scope="project"):
    row = write_prompt_file("chief", name, body, project_root=proj, scope=scope)
    assert row is not None
    return row


def test_actions_are_the_seven():
    assert ACTIONS == ("read", "post", "plan", "decide", "run", "stop", "answer")
    assert frozenset(ACTIONS) == ALL


def test_the_three_action_sets():
    assert actions_for("status") == frozenset({"read"})
    assert actions_for("planner") == frozenset({"read", "post", "plan"})
    assert actions_for("operator") == ALL
    assert set(TIERS) == {"status", "planner", "operator"}


def test_actions_for_returns_a_frozenset():
    for tier in TIERS:
        assert isinstance(actions_for(tier), frozenset)


def test_an_unknown_tier_gets_the_status_actions():
    assert actions_for("admin") == actions_for("status")
    assert actions_for("") == actions_for("status")


def test_tiers_cannot_be_edited_in_place():
    with pytest.raises(TypeError):
        TIERS["status"] = ALL
    assert actions_for("status") == frozenset({"read"})


@pytest.mark.parametrize(
    "value, tier",
    [
        ("planner", "planner"),
        ("  Planner  ", "planner"),
        ("OPERATOR", "operator"),
        ("status", "status"),
        ("admin", "status"),
        ("", "status"),
        ("   ", "status"),
        ("planner operator", "status"),
        (None, "status"),
    ],
)
def test_normalise_tier(value, tier):
    assert normalise_tier(value) == tier


@pytest.mark.parametrize("name", ["status", "planner", "operator"])
def test_built_in_names_resolve_to_themselves_with_no_files(proj, name):
    assert resolve_preset_tier(name, proj) == name
    assert resolve_preset_tier(name, None) == name


def test_a_project_file_with_no_front_matter_is_status(proj):
    _preset(proj, "operator", "# Operator\nDo everything.")
    assert resolve_preset_tier("operator", proj) == "status"


def test_a_file_with_front_matter_but_no_tier_is_status(proj):
    _preset(proj, "operator", "---\nlabel: Operator\n---\nDo everything.\n")
    assert resolve_preset_tier("operator", proj) == "status"


def test_tier_planner_in_front_matter_resolves_to_planner(proj):
    _preset(proj, "mine", "---\ntier: Planner\n---\n# Mine\nPlan things.\n")
    assert resolve_preset_tier("mine", proj) == "planner"


def test_tier_operator_in_front_matter_resolves_to_operator(proj):
    _preset(proj, "ops", "---\ntier: operator\nlabel: Ops\n---\nRun things.\n")
    assert resolve_preset_tier("ops", proj) == "operator"


def test_tier_admin_is_status(proj):
    _preset(proj, "mine", "---\ntier: admin\n---\nBody.\n")
    assert resolve_preset_tier("mine", proj) == "status"


def test_a_file_decides_even_for_a_built_in_name(proj):
    _preset(proj, "operator", "---\ntier: planner\n---\nOperator, downgraded.\n")
    _preset(proj, "status", "---\ntier: operator\n---\nStatus, upgraded by its file.\n")
    assert resolve_preset_tier("operator", proj) == "planner"
    assert resolve_preset_tier("status", proj) == "operator"


def test_a_project_file_overrides_a_global_file_of_the_same_name(proj):
    _preset(proj, "mine", "---\ntier: operator\n---\nGlobal.\n", scope="global")
    assert resolve_preset_tier("mine", proj) == "operator"
    _preset(proj, "mine", "---\ntier: planner\n---\nProject.\n")
    assert resolve_preset_tier("mine", proj) == "planner"
    assert resolve_preset_tier("mine", None) == "operator"


def test_a_global_file_is_found_when_the_project_has_none(proj):
    _preset(proj, "mine", "---\ntier: planner\n---\nGlobal.\n", scope="global")
    assert resolve_preset_tier("mine", proj) == "planner"


def test_only_the_leading_block_counts(proj):
    _preset(proj, "mine", "Intro.\n\n---\ntier: operator\n---\nBody.\n")
    assert resolve_preset_tier("mine", proj) == "status"


def test_only_a_top_level_tier_line_counts(proj):
    _preset(proj, "mine", "---\nmeta:\n  tier: operator\n---\nBody.\n")
    assert resolve_preset_tier("mine", proj) == "status"


def test_a_tier_line_in_the_body_is_ignored(proj):
    _preset(proj, "mine", "---\nlabel: Mine\n---\ntier: operator\n")
    assert resolve_preset_tier("mine", proj) == "status"


def test_a_prompt_in_another_category_does_not_count(proj):
    write_prompt_file(
        "analyze", "mine", "---\ntier: operator\n---\nBody.\n", project_root=proj
    )
    assert resolve_preset_tier("mine", proj) == "status"


def test_an_unknown_preset_is_status(proj):
    assert resolve_preset_tier("nobody", proj) == "status"
    assert resolve_preset_tier("", proj) == "status"


@pytest.mark.parametrize(
    "name",
    [
        "../x",
        "..",
        "a/b",
        "../../etc/passwd",
        "operator\n",
        " operator",
        "Operator",
        "x y",
    ],
)
def test_a_malformed_or_unmatched_name_is_status(proj, name):
    assert resolve_preset_tier(name, proj) == "status"


def test_a_name_that_climbs_out_cannot_reach_another_file(proj):
    """``chief/../x`` must not read ``prompts/x.md``; the file below stays unread."""
    write_prompt_file(
        "analyze", "x", "---\ntier: operator\n---\nBody.\n", project_root=proj
    )
    assert resolve_preset_tier("../analyze/x", proj) == "status"
    assert resolve_preset_tier("../x", proj) == "status"


def test_strip_front_matter_removes_the_block_and_keeps_the_body():
    text = "---\ntier: planner\nlabel: Mine\n---\n# Mine\n\nPlan things.\n"
    assert strip_front_matter(text) == "# Mine\n\nPlan things.\n"


def test_strip_front_matter_leaves_text_without_a_block_alone():
    assert strip_front_matter("# Mine\nPlan things.\n") == "# Mine\nPlan things.\n"
    assert strip_front_matter("") == ""


def test_strip_front_matter_removes_one_block_only():
    text = "---\ntier: planner\n---\nBody.\n\n---\nnot: front matter\n---\nMore.\n"
    assert strip_front_matter(text) == "Body.\n\n---\nnot: front matter\n---\nMore.\n"


# --- the tier is read from the block that strip_front_matter removes ---------------------------

TIER_BLOCK = "---\ntier: operator\n---\n"


def _block(text: str) -> str:
    """What ``strip_front_matter`` removed from the text: the block the tier is read from."""
    return text[: len(text) - len(strip_front_matter(text))]


@pytest.mark.parametrize(
    "text, block, raw_tier",
    [
        pytest.param(
            TIER_BLOCK, TIER_BLOCK, " operator", id="ends-at-the-end-of-the-text"
        ),
        pytest.param(
            TIER_BLOCK + "\n\nBody.\n",
            TIER_BLOCK + "\n\n",
            " operator",
            id="trailing-blank-lines-go-with-the-block",
        ),
        pytest.param(
            TIER_BLOCK + "Body.\n", TIER_BLOCK, " operator", id="followed-by-a-body"
        ),
        pytest.param(
            "---\ntier: operator\n---",
            "",
            None,
            id="no-line-break-after-the-closing-line",
        ),
        pytest.param(
            "---\r\ntier: operator\r\n---\r\nBody.\r\n", "", None, id="crlf-is-no-block"
        ),
        pytest.param("---\ntier: operator\nBody.\n", "", None, id="never-closed"),
        pytest.param("Body.\n", "", None, id="no-front-matter"),
        pytest.param("", "", None, id="empty"),
    ],
)
def test_the_tier_is_read_from_the_block_strip_front_matter_removes(
    text, block, raw_tier
):
    assert _block(text) == block
    assert _front_matter_tier(text) == raw_tier
    assert normalise_tier(_front_matter_tier(text)) == (
        "operator" if raw_tier else "status"
    )


def test_the_text_a_chief_is_given_never_holds_the_block_its_tier_came_from():
    for text in (TIER_BLOCK + "Body.\n", TIER_BLOCK, TIER_BLOCK + "\n\nBody.\n"):
        assert _block(text) + strip_front_matter(text) == text
        assert "tier:" not in strip_front_matter(text)


@pytest.mark.parametrize(
    "quoted", ['"operator"', "'operator'", '"operator', "operator'"]
)
def test_a_quoted_tier_is_status(proj, quoted):
    """The value is read as written, with its quotes, and a quoted name is no tier name."""
    text = f"---\ntier: {quoted}\n---\nBody.\n"
    _preset(proj, "mine", text)

    assert _front_matter_tier(text) == f" {quoted}"
    assert normalise_tier(_front_matter_tier(text)) == "status"
    assert resolve_preset_tier("mine", proj) == "status"
