"""Shim — re-exports from pathly_orchestrator.skills.parser for backward compat."""
from pathly_orchestrator.skills.parser import *  # noqa: F401, F403
from pathly_orchestrator.skills.parser import (  # noqa: F401
    parse_skill_body,
    parse_skill_document,
    serialize_skill_document,
    split_frontmatter,
)
