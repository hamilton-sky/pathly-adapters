"""chief-agent 20, B18: the tier line is read from the lines the pasted text has.

``_front_matter_tier`` split the front matter with ``str.splitlines()``, which also breaks at
U+2028, U+2029, ``\\x85``, ``\\x0b``, ``\\x0c`` and ``\\x1c`` to ``\\x1e``. ``strip_front_matter``, which
makes the pasted text, knows only ``\\n``. A prompt file whose ``description:`` line holds one of
them followed by ``tier: operator`` was therefore read as tier ``operator`` while the pasted
text shows it as part of the description. The block is now split on ``"\\n"`` only.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.skills.prompt_files import write_prompt_file
from pathly_orchestrator.supervisor.chief_tiers import (
    resolve_preset_tier,
    strip_front_matter,
)

BREAKS = [" ", " ", "\x85", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"]
IDS = ["u2028", "u2029", "x85", "x0b", "x0c", "x1c", "x1d", "x1e"]


@pytest.fixture()
def proj(tmp_path):
    return str(tmp_path / "proj")


def _tier(proj: str, body: str) -> str:
    row = write_prompt_file("chief", "x", body, project_root=proj, scope="project")
    assert row is not None
    return resolve_preset_tier("x", proj)


@pytest.mark.parametrize("char", BREAKS, ids=IDS)
def test_a_tier_after_a_character_splitlines_breaks_at_inside_a_value_is_not_a_tier_line(
    proj, char
):
    body = f"---\ndescription: a{char}tier: operator\n---\nDo everything.\n"

    assert _tier(proj, body) == "status"
    assert f"description: a{char}tier: operator" not in strip_front_matter(body)


@pytest.mark.parametrize("char", BREAKS, ids=IDS)
def test_a_tier_that_starts_after_such_a_character_is_not_a_tier_line_either(
    proj, char
):
    body = f"---\nlabel: x\n{char}tier: operator\n---\nDo everything.\n"

    assert _tier(proj, body) == "status"


@pytest.mark.parametrize("char", BREAKS, ids=IDS)
def test_a_real_tier_line_after_a_value_that_holds_such_a_character_still_counts(
    proj, char
):
    body = f"---\ndescription: a{char}b\ntier: operator\n---\nDo everything.\n"

    assert _tier(proj, body) == "operator"


def test_a_plain_tier_line_gives_its_tier(proj):
    assert _tier(proj, "---\ntier: operator\n---\nDo everything.\n") == "operator"


def test_the_same_with_crlf_line_ends_gives_the_tier(proj):
    body = "---\r\nlabel: x\r\ntier: operator\r\n---\r\nDo everything.\r\n"

    assert _tier(proj, body) == "operator"


def test_a_lone_carriage_return_is_a_line_end_the_pasted_text_shares(proj):
    """The file is read in text mode, where a lone ``\\r`` is a line end for the pasted text too."""
    body = "---\ndescription: a\rtier: operator\n---\nDo everything.\n"

    assert _tier(proj, body) == "operator"
