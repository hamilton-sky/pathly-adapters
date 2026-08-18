"""Reading the composition manifest, skill bodies, and fragments off disk.

The manifest is the packaged ``core/skills/composition.yaml``, optionally overlaid per project
from the DB (``load_effective_manifest``). Everything here is I/O; no assembly happens.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Any

import yaml


def _skills_root():
    return files("pathly_data").joinpath("core/skills")


def load_manifest() -> dict:
    """Read and parse ``core/skills/composition.yaml`` (the version-controlled default)."""
    text = _skills_root().joinpath("composition.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def load_artifact_manifest() -> dict:
    """Load artifact-manifest.yaml (role->file->gate). Mirrors load_manifest."""
    text = _skills_root().joinpath("artifact-manifest.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text) or {}


def manifest_role_file(role: str, skill: str | None = None) -> tuple[str, str] | None:
    """Resolve (file, gate) for a role, honoring (role, skill) overrides first.

    Returns None when the role has no manifest entry (the allow-list gate).
    """
    m = load_artifact_manifest()
    overrides = m.get("overrides", {}) or {}
    if skill and f"{role}.{skill}" in overrides:
        e = overrides[f"{role}.{skill}"]
        return (e["file"], e["gate"])
    roles = m.get("roles", {}) or {}
    if role in roles:
        e = roles[role]
        return (e["file"], e["gate"])
    return None


def load_effective_manifest(project_root: str | None = None) -> dict:
    """The composition manifest with per-project DB overrides merged over the packaged
    YAML defaults.

    The YAML stays the source of truth; rows in ``skill_composition`` (written by the
    skill editor) replace a skill's ``fragments`` list. **Fail-safe:** any DB error or
    absent override layer returns the pure YAML manifest, so the runner / install path
    never breaks because of this layer. With no overrides the result is identical to
    :func:`load_manifest`.
    """
    base = load_manifest()
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.skill_composition import (
            get_composition_overrides,
        )

        overrides = get_composition_overrides(get_db(project_root), project_root)
    except Exception:
        return base
    if not overrides:
        return base
    merged = dict(base)
    skills = dict(base.get("skills") or {})
    for skill_key, fragments in overrides.items():
        entry = dict(skills.get(skill_key) or {})
        entry["fragments"] = list(fragments)
        skills[skill_key] = entry
    merged["skills"] = skills
    return merged


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
