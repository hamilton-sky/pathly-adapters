"""Skill fragment composition — assemble stage skills from reusable fragments.

One resolver serves both skill-delivery modes:
  - runtime:    ``build_prompt()`` composes the runner skill (``team/*``) for the live adapter
  - build-time: ``pathly-setup`` / ``stitch_skill`` composes the installed skill (``development/*``)

The manifest (``core/skills/composition.yaml``) is keyed by the core-skills-relative
skill path without the ``.md`` suffix — e.g. ``team/build``, ``development/build``.

Composition contract:
    assembled = [stage skill body] + [defaults + skill fragments, in declared order]
  - ``defaults`` apply ONLY to skills present in the ``skills:`` map.
  - A skill ABSENT from ``skills:`` is returned raw and unchanged (no fragments, no defaults).
  - A fragment entry is either a bare name (``feedback-protocol``) or an object with a gate
    (``{name: spawn-rules, requires: can_spawn}``); a gated fragment is dropped when the active
    adapter's capability flag is false.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml

# Capabilities a fragment may gate on via ``requires:``. Extend as adapters grow.
_KNOWN_CAPABILITIES = {"can_spawn"}

# Adapters whose ``_meta`` capability flags we can derive caps from.
_KNOWN_ADAPTERS = {"claude", "codex", "copilot", "antigravity"}


# ── Resource helpers ────────────────────────────────────────────────────────────


def _skills_root():
    return files("pathly_data").joinpath("core/skills")


def load_manifest() -> dict:
    """Read and parse ``core/skills/composition.yaml``."""
    text = _skills_root().joinpath("composition.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def _read_skill_body(skill: str) -> str:
    return _skills_root().joinpath(f"{skill}.md").read_text(encoding="utf-8")


def _skill_exists(skill: str) -> bool:
    return _skills_root().joinpath(f"{skill}.md").is_file()


def _read_fragment(fragments_dir: str, name: str) -> str:
    return (
        _skills_root()
        .joinpath(f"{fragments_dir}/{name}.md")
        .read_text(encoding="utf-8")
    )


def _known_fragments(fragments_dir: str) -> set[str]:
    root = _skills_root().joinpath(fragments_dir)
    names: set[str] = set()
    for entry in root.iterdir():
        if entry.name.endswith(".md"):
            names.add(entry.name[:-3])
    return names


def _entry_parts(entry: Any) -> tuple[str, str | None]:
    """Normalize a fragment entry into ``(name, requires)``."""
    if isinstance(entry, str):
        return entry, None
    if isinstance(entry, dict):
        name = entry.get("name")
        if not name or not isinstance(name, str):
            raise ValueError(
                f"composition: fragment object missing a 'name' string: {entry!r}"
            )
        return name, entry.get("requires")
    raise ValueError(
        f"composition: fragment entry must be a string or object, got {entry!r}"
    )


# ── Adapter capabilities ──────────────────────────────────────────────────────


def adapter_caps_for(adapter: str) -> dict:
    """Derive capability flags for an adapter from its ``_meta/*.yaml`` files.

    Currently derives ``can_spawn``: true when any agent meta declares a non-empty
    ``can_spawn`` list. Raises ``ValueError`` for an unknown adapter.
    """
    adapter = adapter or "claude"
    if adapter not in _KNOWN_ADAPTERS:
        raise ValueError(
            f"composition: unknown adapter {adapter!r}; known adapters: {sorted(_KNOWN_ADAPTERS)}"
        )
    meta_dir = files("pathly_data").joinpath(f"adapters/{adapter}/_meta")
    can_spawn = False
    try:
        for entry in meta_dir.iterdir():
            if not entry.name.endswith(".yaml"):
                continue
            try:
                meta = yaml.safe_load(entry.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            if meta.get("can_spawn"):
                can_spawn = True
                break
    except (FileNotFoundError, OSError):
        pass
    return {"can_spawn": can_spawn}


def _coerce_caps(adapter_caps: Any) -> dict:
    """Accept either a caps dict or an adapter-name string."""
    if adapter_caps is None:
        return {}
    if isinstance(adapter_caps, str):
        return adapter_caps_for(adapter_caps)
    if isinstance(adapter_caps, dict):
        return adapter_caps
    raise ValueError(
        f"composition: adapter_caps must be a dict or adapter-name str, got {type(adapter_caps).__name__}"
    )


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
    parts = [skill_body.rstrip()] + fragment_bodies
    return "\n\n".join(parts) + "\n"


def compose_skill(
    skill: str, adapter_caps: Any, *, manifest: dict | None = None
) -> str:
    """Return the assembled markdown for ``skill`` under the given adapter caps.

    ``adapter_caps`` may be a caps dict (``{"can_spawn": True}``) or an adapter-name
    string (``"claude"``), which is resolved via :func:`adapter_caps_for`.

    A skill absent from the manifest's ``skills:`` map is returned raw and unchanged,
    preserving current behaviour until it is explicitly converted.
    """
    if manifest is None:
        manifest = load_manifest()
    skills_map = manifest.get("skills") or {}
    raw = _read_skill_body(skill)
    if skill not in skills_map:
        return raw

    caps = _coerce_caps(adapter_caps)
    fragments_dir = manifest.get("fragments_dir", "fragments")
    spec = skills_map[skill] or {}
    entries = list(manifest.get("defaults") or []) + list(spec.get("fragments") or [])

    parts = [raw.rstrip("\n")]
    for entry in entries:
        name, requires = _entry_parts(entry)
        if requires and not caps.get(requires):
            continue  # gated out for this adapter
        parts.append(_read_fragment(fragments_dir, name).rstrip("\n"))
    return "\n\n".join(parts) + "\n"


# ── Validator ─────────────────────────────────────────────────────────────────


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
