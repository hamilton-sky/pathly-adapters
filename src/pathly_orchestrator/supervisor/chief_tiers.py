"""What a chief may do, and which tier a chosen preset names.

The action lists are code. A chief preset is user-editable text (and any worker with file
access can edit it), so it never lists actions: it only names one of the three tiers below
with a leading front-matter ``tier:`` line, and the server alone decides what that tier
allows. A missing or unknown tier, an unknown preset or a malformed preset name is ``status``
(read-only).
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from pathly_orchestrator.skills.compose_base import _strip_leading_frontmatter
from pathly_orchestrator.skills.prompt_files import read_prompt_file

ACTIONS = ("read", "post", "plan", "decide", "run", "stop", "answer")

TIERS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "status": frozenset({"read"}),
        "planner": frozenset({"read", "post", "plan"}),
        "operator": frozenset(ACTIONS),
    }
)

_DEFAULT_TIER = "status"


def actions_for(tier: str) -> frozenset[str]:
    """The tier's actions; an unknown tier gets ``status``'s."""
    return TIERS.get(tier, TIERS[_DEFAULT_TIER])


def normalise_tier(value: object) -> str:
    """Lower-cased and stripped; anything that is not a tier is ``status``."""
    tier = str(value or "").strip().lower()
    return tier if tier in TIERS else _DEFAULT_TIER


def strip_front_matter(text: str) -> str:
    """The text with one leading front-matter block removed."""
    return _strip_leading_frontmatter(text)


def _front_matter_tier(text: str) -> str | None:
    """The value of the ``tier:`` line of the leading front-matter block, else None.

    The block is exactly what ``strip_front_matter`` removes, so the text that is pasted and
    the text that was read for the tier cannot disagree. Only an unindented ``tier:`` line
    counts; every other key is ignored. The value is returned as written, so a quoted one
    (``tier: "operator"``) keeps its quotes, is not a tier name, and resolves to ``status``.
    The block is split on ``"\n"`` only, the one line break
    ``strip_front_matter`` knows: ``str.splitlines`` also breaks at U+2028, U+2029, ``\x85``,
    ``\x0b``, ``\x0c`` and ``\x1c`` to ``\x1e``, which would read a ``tier:`` out of the middle
    of a line the pasted text shows whole.
    """
    block = text[: len(text) - len(strip_front_matter(text))]
    for line in block.split("\n")[1:]:
        if line.startswith("tier:"):
            return line[len("tier:") :]
    return None


def resolve_preset_tier(preset: str, project_root: str | None) -> str:
    """The tier the preset ``chief/<preset>`` names.

    A user prompt file (project over global, as ``read_prompt_file`` merges them) decides
    through its front matter, and a file with no ``tier:`` is ``status``. With no file the
    built-in names ``status``, ``planner`` and ``operator`` map to themselves; anything else,
    including a name ``read_prompt_file`` rejects, is ``status``.
    """
    row = read_prompt_file(f"chief/{preset}", project_root)
    if row is not None:
        return normalise_tier(_front_matter_tier(row["body"]))
    return preset if preset in TIERS else _DEFAULT_TIER
