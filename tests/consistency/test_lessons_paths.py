"""The cross-feature lessons pipeline must agree on ONE path.

This pipeline was dead: `utilities/lessons.md` told the agent to write
`LESSONS.md` "in the project root", `planning/plan.md` told the planner to read
it from the project root, and the files actually live in `pathly/lessons/` —
the location the root CLAUDE.md layout table documents. No code reads them
(`grep LESSONS src/ studio/src/` is empty); the only reader is an agent
following a skill, so the mismatch produced no error, no log line, and no
symptom. Retro wrote candidates, the lessons skill distilled them, and the
planner then read nothing — silently, every run.

These tests pin the agreement so the pipeline cannot come apart again the same
quiet way.
"""

from __future__ import annotations

import re

import pytest

from tests._paths import SRC

_SKILLS = SRC / "pathly_data/core/skills"
_CANONICAL_DIR = "pathly/lessons/"

# Every skill that names a lessons file, and what it does with it.
_LESSONS_SKILLS = [
    "planning/retro.md",
    "planning/plan.md",
    "utilities/lessons.md",
    "utilities/archive.md",
    "team/retro.md",
    "controls/end.md",
]

# A lessons filename NOT preceded by the canonical directory.
_BARE_REF = re.compile(r"(?<!lessons/)\bLESSONS(?:_CANDIDATE)?\.md\b")


@pytest.mark.parametrize("rel", _LESSONS_SKILLS)
def test_every_lessons_reference_is_canonically_pathed(rel):
    """No skill may name LESSONS.md without the pathly/lessons/ prefix."""
    text = (_SKILLS / rel).read_text(encoding="utf-8")
    bare = _BARE_REF.findall(text)
    assert not bare, (
        f"{rel}: {len(bare)} unqualified lessons reference(s) — "
        f"every mention must be prefixed with {_CANONICAL_DIR!r}"
    )


@pytest.mark.parametrize("rel", _LESSONS_SKILLS)
def test_no_skill_still_points_lessons_at_the_project_root(rel):
    """The specific wording that broke it: 'LESSONS… in the project root'."""
    text = (_SKILLS / rel).read_text(encoding="utf-8")
    for line in text.splitlines():
        if "LESSONS" in line:
            assert "project root" not in line.lower(), f"{rel}: {line.strip()!r}"


def test_writer_and_reader_agree_on_the_same_file():
    """The distiller writes exactly what the planner reads — the dead link."""
    writer = (_SKILLS / "utilities/lessons.md").read_text(encoding="utf-8")
    reader = (_SKILLS / "planning/plan.md").read_text(encoding="utf-8")
    target = f"{_CANONICAL_DIR}LESSONS.md"
    assert target in writer, "lessons skill must name the canonical write target"
    assert target in reader, "planner must read the same path the lessons skill writes"


def test_candidate_producers_and_consumers_agree():
    """retro appends candidates; archive/end trigger distillation from them."""
    target = f"{_CANONICAL_DIR}LESSONS_CANDIDATE.md"
    for rel in ("planning/retro.md", "team/retro.md"):
        assert target in (_SKILLS / rel).read_text(
            encoding="utf-8"
        ), f"{rel} (producer)"
    for rel in ("utilities/archive.md", "controls/end.md"):
        assert target in (_SKILLS / rel).read_text(
            encoding="utf-8"
        ), f"{rel} (consumer)"
