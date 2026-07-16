"""Anti-drift guard for the installer's per-adapter skill stitch path.

Converted development/* skills are NOT committed as materialized adapter files —
``pathly-setup <host> --apply`` writes them to the live install dirs at install
time. So the meaningful staleness guard is structural: stitching each converted
skill through the real installer composition path (`_compose_or_read`, the same
function `stitch_skill` calls) must, for every adapter, yield the COMPOSED body
(not the raw stage body) with each shared section appearing exactly once.

This catches two regressions a golden snapshot alone would miss:
  * a converted skill silently falling back to raw (manifest entry dropped, or
    the compose path raising and the resilient installer swallowing it), and
  * a shared section materializing twice for some adapter (body + fragment
    duplication once adapter gating is threaded through).
"""

import pytest

from install_cli.resources import core_skills_path
from install_cli.stitch import _compose_or_read
from pathly_orchestrator.compose import _read_skill_body

# Adapters that materialize development/* skills via pathly-setup.
_ADAPTERS = ["claude", "codex", "copilot"]

# Converted skills installed by pathly-setup (group "development").
_CONVERTED_DEV_SKILLS = ["development/build", "development/review", "development/test"]

_SHARED_SECTIONS = [
    "## Live progress logging",
    "## Completion report",
    "## Scout choreography",
    "## Feedback protocol",
    "## Sub-agent spawning rules",
]


def _core_path(skill: str):
    group, name = skill.split("/", 1)
    return core_skills_path() / group / f"{name}.md"


@pytest.mark.parametrize("adapter", _ADAPTERS)
@pytest.mark.parametrize("skill", _CONVERTED_DEV_SKILLS)
def test_stitch_composes_not_raw_for_every_adapter(adapter, skill):
    """The installer must compose (never silently fall back to raw) per adapter."""
    core_path = _core_path(skill)
    raw = _read_skill_body(skill)
    composed = _compose_or_read(core_path, skill, adapter)
    assert composed != raw, f"{skill} fell back to raw for adapter {adapter!r}"


@pytest.mark.parametrize("adapter", _ADAPTERS)
@pytest.mark.parametrize("skill", _CONVERTED_DEV_SKILLS)
def test_stitch_shared_sections_appear_at_most_once(adapter, skill):
    """No shared section may materialize twice for any adapter."""
    core_path = _core_path(skill)
    composed = _compose_or_read(core_path, skill, adapter)
    for heading in _SHARED_SECTIONS:
        assert (
            composed.count(heading) <= 1
        ), f"{skill} duplicated {heading!r} for adapter {adapter!r}"


@pytest.mark.parametrize("adapter", _ADAPTERS)
def test_stitch_unconverted_skill_stays_raw(adapter):
    """A skill absent from the manifest must stitch to its raw body for every adapter."""
    skill = "development/fix"
    core_path = _core_path(skill)
    raw = _read_skill_body(skill)
    assert _compose_or_read(core_path, skill, adapter) == raw
