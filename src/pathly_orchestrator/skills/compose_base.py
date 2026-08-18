"""Composition constants and the dash-safety strip.

Leaf module — every other ``compose_*`` module depends on this and it depends on none of
them, which is what keeps the composition package acyclic.
"""

from __future__ import annotations

import re

# Capabilities a fragment may gate on via ``requires:``. Extend as adapters grow.
_KNOWN_CAPABILITIES = {"can_spawn", "goal_id"}

# Adapters whose ``_meta`` capability flags we can derive caps from.
_KNOWN_ADAPTERS = {"claude", "codex", "copilot", "antigravity"}

# Default board-fragment bundle given to a skill ABSENT from the manifest that is run on a
# board (/comms/run) or in a flow (``board_default=True``). Used only when the manifest has no
# explicit ``board_defaults:`` key. Keeps a custom skill wired to the board: ``comms-post``
# (post artifacts/findings) + ``progress-logging`` (phase telemetry). Board *context* injection
# is separate — it happens at the run level (start_board_run / retrieve_board_context).
_BOARD_DEFAULT_FRAGMENTS = ["progress-logging", "comms-post"]

# A composed prompt must NOT start with ``---``: it is delivered to the CLI via a
# ``-p`` argv token, and an argument starting with ``--`` is parsed as an unknown
# option (e.g. claude: ``error: unknown option '---...'``). Several skill bodies
# begin with ``---\n\n---`` (empty/doubled rule) or real frontmatter (team/team).
_LEADING_FRONTMATTER_RE = re.compile(r"^---[ \t]*\n.*?\n---[ \t]*\n", re.DOTALL)


def _strip_leading_frontmatter(text: str) -> str:
    """Drop a leading YAML-frontmatter / horizontal-rule block from a skill body."""
    if not text.startswith("---"):
        return text
    m = _LEADING_FRONTMATTER_RE.match(text)
    if not m:
        return text
    return text[m.end() :].lstrip("\n")
