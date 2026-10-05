"""Adopt skill files Pathly wrote but the manifest lost.

Repair, prune and ``--uninstall`` only touch manifest-owned files. A skill dir that is on
disk but absent from the manifest (a manifest rewritten by a partial run, an older
install…) therefore survives every one of them — a trim leaves it behind and an uninstall
never removes it. Adoption records it in the manifest so it is reconciled like the rest.

The ownership test is deliberately narrow, because a tracked file can later be deleted:

* the file sits at the exact path Pathly writes for a known skill, and
* its frontmatter ``name:`` equals that skill's ``skill:`` key — the signature the stitcher
  writes — so it is provably Pathly-generated rather than a same-named hand-written skill.

Anything else at a Pathly path (a foreign frontmatter, a symlinked dir the user manages) is
left untouched with a warning; ``--force`` still takes such a file over explicitly.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

from .materialize import adopt, owned_names
from .skill_catalog import SkillInfo, load_catalog

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---", re.DOTALL)


def frontmatter_name(path: Path) -> str | None:
    """The ``name:`` of a skill file's YAML frontmatter, or None if absent/unreadable."""
    try:
        head = path.read_text(encoding="utf-8")[:4096]
        match = _FRONTMATTER.match(head)
        meta = yaml.safe_load(match.group(1)) if match else None
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return None
    name = meta.get("name") if isinstance(meta, dict) else None
    return name if isinstance(name, str) else None


def find_untracked(
    catalog: dict[str, SkillInfo], skills_dest: Path, owned: set[str]
) -> tuple[list[str], dict[str, str]]:
    """Untracked skill files at Pathly's paths: ``(adoptable, {foreign file: why not})``."""
    adoptable: list[str] = []
    foreign: dict[str, str] = {}
    for info in catalog.values():
        path = skills_dest / info.filename
        if info.filename in owned or not path.is_file():
            continue
        parent = skills_dest / info.dirname if info.dirname else None
        if path.is_symlink() or (parent is not None and parent.is_symlink()):
            foreign[info.filename] = "it is a symlink (user-managed)"
        elif (found := frontmatter_name(path)) == info.key:
            adoptable.append(info.filename)
        else:
            foreign[info.filename] = (
                f"its frontmatter name is {found!r}, not {info.key!r}, "
                "so it does not look Pathly-generated"
            )
    return adoptable, foreign


def adopt_untracked(
    host: str,
    skills_dest: Path,
    catalog: dict[str, SkillInfo],
    *,
    dry_run: bool = False,
) -> list[str]:
    """Adopt (or, in a dry run, report) untracked Pathly skill files. Returns their names."""
    if not skills_dest.is_dir():
        return []
    adoptable, foreign = find_untracked(catalog, skills_dest, owned_names(skills_dest))
    for name, why in sorted(foreign.items()):
        print(
            f"  [warn] [{host}] not adopting {skills_dest / name}: {why} "
            "(left untouched; --force takes it over)",
            file=sys.stderr,
        )
    if not adoptable:
        return []
    if dry_run:
        print(
            f"\n[{host}] Would adopt {len(adoptable)} untracked Pathly skill file(s) "
            f"into the manifest in {skills_dest}:"
        )
    else:
        adoptable = adopt(skills_dest, adoptable)
        print(
            f"[{host}] Adopted {len(adoptable)} untracked Pathly skill file(s) "
            f"into the manifest in {skills_dest}:"
        )
    for name in adoptable:
        print(f"  {skills_dest / name}")
    return adoptable


def adopt_untracked_for_host(
    host: str, install_cfg: dict, *, dry_run: bool = False
) -> list[str]:
    """``adopt_untracked`` for a host's skills destination (no-op if it has none)."""
    skills_cfg = install_cfg.get("skills")
    if not skills_cfg:
        return []
    return adopt_untracked(
        host,
        Path(skills_cfg["destination"]).expanduser(),
        load_catalog(host, nested=skills_cfg.get("structure") == "nested"),
        dry_run=dry_run,
    )
