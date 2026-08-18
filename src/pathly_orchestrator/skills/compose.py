"""Skill fragment composition — assemble stage skills from reusable fragments.

One resolver serves both skill-delivery modes:
  - runtime:    ``build_prompt()`` composes the runner skill (``team/*``) for the live adapter
  - build-time: ``pathly-setup`` / ``stitch_skill`` composes the installed skill (``development/*``)

The manifest (``core/skills/composition.yaml``) is keyed by the core-skills-relative
skill path without the ``.md`` suffix — e.g. ``team/build``, ``development/build``.

Composition contract:
    assembled = [stage skill body] + [defaults + skill fragments, in declared order]
  - ``defaults`` apply ONLY to skills present in the ``skills:`` map.
  - A skill ABSENT from ``skills:`` is returned raw and unchanged (no fragments, no defaults)
    — UNLESS ``compose_skill`` is called with ``board_default=True`` (the board-run / flow
    paths do this for a genuinely custom skill), in which case the unrecognized skill instead
    composes the ``board_defaults`` bundle (``progress-logging`` + ``comms-post``) so a
    user-created skill run on a board still reads + posts to it. Build-time install and
    editor-preview paths leave ``board_default`` False, preserving the raw contract.
  - A fragment entry is either a bare name (``feedback-protocol``) or an object with a gate
    (``{name: spawn-rules, requires: can_spawn}``); a gated fragment is dropped when the active
    adapter's capability flag is false.
"""

from __future__ import annotations

from typing import Any

from .compose_base import (
    _KNOWN_CAPABILITIES,
    _KNOWN_ADAPTERS,
    _BOARD_DEFAULT_FRAGMENTS,
    _strip_leading_frontmatter,
)
from .compose_caps import adapter_caps_for, build_adapter_caps, _coerce_caps
from .compose_resources import (
    _skills_root,
    load_manifest,
    load_artifact_manifest,
    manifest_role_file,
    load_effective_manifest,
    _read_skill_body,
    _skill_exists,
    _read_fragment,
    _known_fragments,
    _entry_parts,
)
from .compose_segments import (
    compose_skill_segments,
    segments_to_prompt,
    _body_segment,
    _fragment_segment,
)
from .compose_validate import validate_composition

__all__ = [
    "_KNOWN_CAPABILITIES",
    "_KNOWN_ADAPTERS",
    "_BOARD_DEFAULT_FRAGMENTS",
    "_strip_leading_frontmatter",
    "_skills_root",
    "load_manifest",
    "load_artifact_manifest",
    "manifest_role_file",
    "load_effective_manifest",
    "_read_skill_body",
    "_skill_exists",
    "_read_fragment",
    "_known_fragments",
    "_entry_parts",
    "adapter_caps_for",
    "build_adapter_caps",
    "_coerce_caps",
    "resolve_block",
    "compose_skill_with_block",
    "compose_skill",
    "compose_skill_segments",
    "segments_to_prompt",
    "_body_segment",
    "_fragment_segment",
    "validate_composition",
]

# ── Resolver ──────────────────────────────────────────────────────────────────


def resolve_block(
    block_name: str,
    adapter_caps: Any,
    *,
    user_blocks: dict | None = None,
    manifest: dict | None = None,
) -> list[str]:
    """Return the list of fragment bodies for ``block_name`` under the given adapter caps.

    ``user_blocks`` entries take precedence over manifest blocks of the same name.
    Raises ``KeyError`` if ``block_name`` is not found in the merged block map.
    """
    caps = _coerce_caps(adapter_caps)
    if manifest is None:
        manifest = load_manifest()
    merged_blocks = {**manifest.get("blocks", {}), **(user_blocks or {})}
    if block_name not in merged_blocks:
        raise KeyError(block_name)
    fragments_dir = manifest.get("fragments_dir", "fragments")
    result: list[str] = []
    for entry in merged_blocks[block_name]:
        name, requires = _entry_parts(entry)
        if requires and not caps.get(requires):
            continue
        result.append(_read_fragment(fragments_dir, name).rstrip())
    return result


def compose_skill_with_block(
    skill: str,
    block_name: str,
    adapter_caps: Any,
    *,
    user_blocks: dict | None = None,
    manifest: dict | None = None,
) -> str:
    """Return the assembled markdown for ``skill`` with ``block_name`` fragments appended."""
    caps = _coerce_caps(adapter_caps)
    if manifest is None:
        manifest = load_manifest()
    skill_body = _read_skill_body(skill)
    fragment_bodies = resolve_block(
        block_name, caps, user_blocks=user_blocks, manifest=manifest
    )
    parts = [_strip_leading_frontmatter(skill_body).rstrip()] + fragment_bodies
    return "\n\n".join(parts) + "\n"


def _assemble(raw: str, entries: list, caps: dict, fragments_dir: str) -> str:
    """Join a skill body with its resolved fragment bodies (gated entries dropped)."""
    parts = [_strip_leading_frontmatter(raw).rstrip("\n")]
    for entry in entries:
        name, requires = _entry_parts(entry)
        if requires and not caps.get(requires):
            continue  # gated out for this adapter
        parts.append(_read_fragment(fragments_dir, name).rstrip("\n"))
    return "\n\n".join(parts) + "\n"


def compose_skill(
    skill: str,
    adapter_caps: Any,
    *,
    manifest: dict | None = None,
    board_default: bool = False,
) -> str:
    """Return the assembled markdown for ``skill`` under the given adapter caps.

    ``adapter_caps`` may be a caps dict (``{"can_spawn": True}``) or an adapter-name
    string (``"claude"``), which is resolved via :func:`adapter_caps_for`.

    A skill absent from the manifest's ``skills:`` map is returned raw and unchanged,
    preserving current behaviour until it is explicitly converted — UNLESS
    ``board_default=True``, which the board-run / flow paths pass for a genuinely custom
    skill. Then the unrecognized skill composes the ``board_defaults`` bundle
    (:data:`_BOARD_DEFAULT_FRAGMENTS` = ``progress-logging`` + ``comms-post`` when the
    manifest declares no ``board_defaults:`` key) so a user-created skill run on a board
    still posts its artifacts/progress back. Build-time install and editor-preview paths
    leave ``board_default`` False, keeping the raw contract. (Board *context* is injected
    separately at the run level — start_board_run / retrieve_board_context.)
    """
    if manifest is None:
        manifest = load_manifest()
    skills_map = manifest.get("skills") or {}
    raw = _read_skill_body(skill)

    # Non-board callers (install, editor preview) keep the exact raw fast-path — no
    # caps coercion, byte-identical body — for a skill absent from the manifest.
    if skill not in skills_map and not board_default:
        return raw

    caps = _coerce_caps(adapter_caps)
    fragments_dir = manifest.get("fragments_dir", "fragments")

    if skill not in skills_map:
        # board_default=True on an unrecognized (custom) skill: hand it the default board
        # bundle so it connects through fragments like every recognized skill. Falls back to
        # the hardcoded bundle when the manifest omits `board_defaults:`.
        board_frags = manifest.get("board_defaults")
        if board_frags is None:
            board_frags = list(_BOARD_DEFAULT_FRAGMENTS)
        return _assemble(raw, board_frags, caps, fragments_dir)

    spec = skills_map[skill] or {}
    # `no_defaults: true` on a skill opts it out of the global defaults (e.g. progress-logging).
    # Pure client transforms (summarize/analyze/split) are one-shot file derivations with no
    # pipeline phases, so the phase-telemetry default is dead weight in their prompt.
    default_frags = (
        [] if spec.get("no_defaults") else list(manifest.get("defaults") or [])
    )
    entries = default_frags + list(spec.get("fragments") or [])
    return _assemble(raw, entries, caps, fragments_dir)
