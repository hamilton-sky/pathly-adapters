"""Shim — re-exports from pathly_orchestrator.skills.compose for backward compat."""

from pathly_orchestrator.skills.compose import *  # noqa: F401, F403
from pathly_orchestrator.skills.compose import (  # noqa: F401
    load_manifest,
    load_artifact_manifest,
    manifest_role_file,
    load_effective_manifest,
    adapter_caps_for,
    resolve_block,
    compose_skill_with_block,
    compose_skill,
    compose_skill_segments,
    segments_to_prompt,
    validate_composition,
    _KNOWN_CAPABILITIES,
    _KNOWN_ADAPTERS,
    _skills_root,
    _read_skill_body,
    _skill_exists,
    _read_fragment,
    _known_fragments,
    _entry_parts,
    _coerce_caps,
)
