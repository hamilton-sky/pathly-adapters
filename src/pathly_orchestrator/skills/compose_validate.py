"""Manifest validation — fail loudly at build time rather than silently at run time."""

from __future__ import annotations

from .compose_base import _KNOWN_CAPABILITIES
from .compose_resources import (
    load_manifest,
    _known_fragments,
    _entry_parts,
    _skill_exists,
)


def validate_composition(manifest: dict | None = None) -> None:
    """Validate the manifest, raising ``ValueError`` on the first problem found.

    Rejects: unknown fragment name, unknown skill name, duplicate include
    (counting defaults), and unknown ``requires:`` capability. A missing fragment
    file referenced by the manifest also fails here.
    """
    if manifest is None:
        manifest = load_manifest()

    fragments_dir = manifest.get("fragments_dir", "fragments")
    known_fragments = _known_fragments(fragments_dir)

    def _check(name: str, where: str) -> None:
        if name not in known_fragments:
            raise ValueError(f"composition: unknown fragment {name!r} in {where}")

    # defaults
    seen_defaults: set[str] = set()
    for entry in manifest.get("defaults") or []:
        name, requires = _entry_parts(entry)
        _check(name, "defaults")
        if requires and requires not in _KNOWN_CAPABILITIES:
            raise ValueError(
                f"composition: unknown capability {requires!r} in defaults"
            )
        if name in seen_defaults:
            raise ValueError(f"composition: duplicate fragment {name!r} in defaults")
        seen_defaults.add(name)

    # board_defaults (optional — absent key falls back to _BOARD_DEFAULT_FRAGMENTS at runtime)
    seen_board_defaults: set[str] = set()
    for entry in manifest.get("board_defaults") or []:
        name, requires = _entry_parts(entry)
        _check(name, "board_defaults")
        if requires and requires not in _KNOWN_CAPABILITIES:
            raise ValueError(
                f"composition: unknown capability {requires!r} in board_defaults"
            )
        if name in seen_board_defaults:
            raise ValueError(
                f"composition: duplicate fragment {name!r} in board_defaults"
            )
        seen_board_defaults.add(name)

    # per-skill
    for skill, spec in (manifest.get("skills") or {}).items():
        if not _skill_exists(skill):
            raise ValueError(
                f"composition: unknown skill {skill!r} (no core/skills/{skill}.md)"
            )
        spec = spec or {}
        seen = set(seen_defaults)
        for entry in spec.get("fragments") or []:
            name, requires = _entry_parts(entry)
            _check(name, f"skill {skill!r}")
            if requires and requires not in _KNOWN_CAPABILITIES:
                raise ValueError(
                    f"composition: unknown capability {requires!r} in skill {skill!r}"
                )
            if name in seen:
                raise ValueError(
                    f"composition: duplicate include {name!r} in skill {skill!r}"
                )
            seen.add(name)

    # blocks (optional — absent key is backward-compatible)
    if "blocks" not in manifest:
        return
    for block_name, entries in manifest["blocks"].items():
        if not isinstance(entries, list):
            raise ValueError(f"blocks[{block_name!r}]: must be a list")
        seen_block: set[str] = set()
        for entry in entries:
            try:
                name, requires = _entry_parts(entry)
            except ValueError as exc:
                raise ValueError(f"blocks[{block_name!r}]: {exc}") from exc
            if name not in known_fragments:
                raise ValueError(f"blocks[{block_name!r}]: unknown fragment {name!r}")
            if requires is not None and requires not in _KNOWN_CAPABILITIES:
                raise ValueError(
                    f"blocks[{block_name!r}]: unknown capability {requires!r}"
                )
            if name in seen_block:
                raise ValueError(f"blocks[{block_name!r}]: duplicate fragment {name!r}")
            seen_block.add(name)
