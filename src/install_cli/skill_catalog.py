"""The installable-skill catalogue of one host adapter, and which of it is installed.

One reader of ``adapters/<host>/_meta/*_skill.yaml`` shared by the installer
(tier gating), ``--list`` / ``--remove`` and the Studio export picker, so "what is a
skill, what is its file, is it a default" is answered in exactly one place.

Skills are addressed by their ``skill:`` key (``build``, ``fsm-call``, ``team/build``) —
what ``--export`` takes — which is *not* the directory name (``pathly-team-build``).
``resolve_skill_args`` accepts either spelling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import yaml

from .resources import adapter_meta_path

# Tier-1 — the only skills installed by default (`--apply`). These are the interactive board
# on-ramps (create-feature, post), the dispatcher/help that make them discoverable, and the
# two operational utilities people actually reach for (status, fsm-call). Every other skill is
# export-on-demand: `pathly-setup <host> --export <skill>` (or `--all-skills` for the lot).
# Keyed by the core skill name (the `skill:` field of each *_skill.yaml meta).
DEFAULT_EXPOSED_SKILLS = frozenset(
    {"pathly", "help", "create-feature", "post", "status", "fsm-call"}
)


@dataclass(frozen=True)
class SkillInfo:
    key: str  # the `skill:` field — what --export / --remove take
    name: str  # meta file stem minus "_skill" (the default directory name stem)
    filename: str  # path under the skills dest, e.g. "pathly-build/SKILL.md"
    meta_file: Path
    meta: dict
    requires: tuple[str, ...] = ()  # `skill:` keys this skill's text tells the host to invoke

    @property
    def default(self) -> bool:
        return self.key in DEFAULT_EXPOSED_SKILLS

    @property
    def dirname(self) -> str:
        """Directory under the skills dest ('' for a flat ``<name>.md`` layout)."""
        head, sep, _ = self.filename.partition("/")
        return head if sep else ""

    def owns(self, manifest_name: str) -> bool:
        """True when a manifest entry is one of this skill's files (SKILL.md or a sibling)."""
        if manifest_name == self.filename:
            return True
        return bool(self.dirname) and manifest_name.startswith(self.dirname + "/")


def load_catalog(host: str, *, nested: bool) -> dict[str, SkillInfo]:
    """Every skill the host's adapter defines, keyed by ``skill:`` (meta-file order)."""
    catalog: dict[str, SkillInfo] = {}
    for meta_file in sorted(adapter_meta_path(host).glob("*_skill.yaml")):
        meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
        if "skill" not in meta:
            raise ValueError(f"Missing required fields in {meta_file}: ['skill']")
        requires = meta.get("requires") or []
        if not isinstance(requires, list) or not all(isinstance(r, str) for r in requires):
            raise ValueError(f"'requires' in {meta_file} must be a list of skill keys")
        name = meta_file.stem.removesuffix("_skill")
        default_filename = f"{name}/SKILL.md" if nested else f"{name}.md"
        catalog[meta["skill"]] = SkillInfo(
            key=meta["skill"],
            name=name,
            filename=meta.get("filename", default_filename),
            meta_file=meta_file,
            meta=meta,
            requires=tuple(requires),
        )
    return catalog


def requires_closure(catalog: dict[str, SkillInfo], keys: Iterable[str]) -> set[str]:
    """``keys`` plus everything they require, transitively.

    A ``requires`` entry that names no skill is a metadata bug, not something to skip: the
    skill would be installed without a skill its own text invokes.
    """
    closure: set[str] = set()
    pending = list(keys)
    while pending:
        key = pending.pop()
        if key in closure:
            continue
        closure.add(key)
        for needed in catalog[key].requires:
            if needed not in catalog:
                raise ValueError(
                    f"skill {key!r} requires {needed!r}, which is not a skill "
                    f"(fix `requires:` in {catalog[key].meta_file.name})"
                )
            pending.append(needed)
    return closure


def dependents_of(
    catalog: dict[str, SkillInfo], key: str, among: Iterable[str]
) -> list[str]:
    """Skills in ``among`` that need ``key`` (directly or through another requirement)."""
    return sorted(
        other
        for other in among
        if other != key and key in requires_closure(catalog, [other])
    )


def installed_keys(catalog: dict[str, SkillInfo], skills_dest: Path) -> set[str]:
    """Skills whose file is on disk under ``skills_dest`` (tracked or not)."""
    return {k for k, info in catalog.items() if (skills_dest / info.filename).is_file()}


def resolve_skill_args(
    catalog: dict[str, SkillInfo], args: Iterable[str]
) -> tuple[list[str], list[str]]:
    """Map user-typed names to catalogue keys. Returns ``(keys, unknown)``.

    Accepts the ``skill:`` key (``team/build``), the on-disk directory name
    (``pathly-team-build``) or the meta stem (``team-build``). Keys win a clash.
    """
    by_alias: dict[str, str] = {}
    for key, info in catalog.items():
        for alias in (info.name, info.dirname or info.filename.removesuffix(".md")):
            by_alias.setdefault(alias, key)
    keys: list[str] = []
    unknown: list[str] = []
    for arg in args:
        key = arg if arg in catalog else by_alias.get(arg)
        if key is None:
            unknown.append(arg)
        elif key not in keys:
            keys.append(key)
    return keys, unknown
