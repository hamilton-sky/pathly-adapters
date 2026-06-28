"""Catalog index rebuilder — walks pathly_data/core and upserts each file.

Imports upsert_catalog_item + helpers from catalog_items; rebuild_catalog is
re-exported from catalog_items for callers that already import from there.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from .catalog_items import _find_data_root, _rel, upsert_catalog_item


def _first_line(path: Path) -> str:
    """Return the first non-heading, non-blank line as a short description."""
    try:
        text = path.read_text(encoding="utf-8")
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                text = text[end + 4:]
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            return line[:200]
    except OSError:
        pass
    return ""


def _parse_frontmatter(
    text: str, fallback_name: str
) -> tuple[str, str, str, str | None]:
    """Extract (name, description, category, requires) from YAML frontmatter."""
    name = fallback_name
    description = ""
    category = ""
    requires: str | None = None
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return name, description, category, requires
    for line in match.group(1).splitlines():
        m = re.match(r"^(\w+):\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip("\"'")
        if key == "name":
            name = value or fallback_name
        elif key == "description":
            description = value
        elif key == "category":
            category = value
        elif key == "requires":
            requires = value or None
    return name, description, category, requires


def _index_agents(conn, core: Path) -> None:
    agents_dir = core / "agents"
    if not agents_dir.exists():
        return
    for f in sorted(agents_dir.rglob("*.md")):
        if "README" in f.name:
            continue
        parts = f.relative_to(agents_dir).parts
        category = parts[0] if len(parts) > 1 else ""
        content = f.read_text(encoding="utf-8")
        upsert_catalog_item(
            conn,
            item_type="agent",
            name=f.stem,
            rel_path=_rel(f, core.parent.parent),
            abs_path=str(f).replace("\\", "/"),
            category=category,
            description=_first_line(f),
            content=content,
        )


def _index_fragments(conn, core: Path) -> None:
    fragments_dir = core / "skills" / "fragments"
    if not fragments_dir.exists():
        return
    for f in sorted(fragments_dir.rglob("*.md")):
        parts = f.relative_to(fragments_dir).parts
        subdir_category = parts[0] if len(parts) > 1 else ""
        content = f.read_text(encoding="utf-8")
        name, description, _, _ = _parse_frontmatter(content, f.stem)
        item_name = f"{subdir_category}/{f.stem}" if subdir_category else name
        upsert_catalog_item(
            conn,
            item_type="fragment",
            name=item_name,
            rel_path=_rel(f, core.parent.parent),
            abs_path=str(f).replace("\\", "/"),
            category=subdir_category or "fragments",
            description=description,
            content=content,
        )


def _index_skills(conn, core: Path, _data_root: Path) -> None:
    skills_dir = core / "skills"
    if not skills_dir.exists():
        return
    for f in sorted(skills_dir.rglob("*.md")):
        parts = f.relative_to(skills_dir).parts
        if parts and parts[0] == "fragments":
            continue
        rel_to_skills = f.relative_to(skills_dir)
        skill_name = str(rel_to_skills.with_suffix("")).replace(os.sep, "/")
        category = parts[0] if len(parts) > 1 else ""
        content = f.read_text(encoding="utf-8")
        upsert_catalog_item(
            conn,
            item_type="skill",
            name=skill_name,
            rel_path=_rel(f, core.parent.parent),
            abs_path=str(f).replace("\\", "/"),
            category=category,
            description=_first_line(f),
            content=content,
        )


def _index_templates(conn, core: Path, _data_root: Path) -> None:
    templates_dir = core / "templates"
    if not templates_dir.exists():
        return
    for f in sorted(templates_dir.rglob("*.md")):
        rel_to_templates = f.relative_to(templates_dir)
        parts = rel_to_templates.parts
        tmpl_name = str(rel_to_templates.with_suffix("")).replace(os.sep, "/")
        category = parts[0] if len(parts) > 1 else ""
        content = f.read_text(encoding="utf-8")
        upsert_catalog_item(
            conn,
            item_type="template",
            name=tmpl_name,
            rel_path=_rel(f, core.parent.parent),
            abs_path=str(f).replace("\\", "/"),
            category=category,
            description=_first_line(f),
            content=content,
        )


def rebuild_catalog(conn) -> None:
    """Walk pathly_data/core and (re)index agents, fragments, skills, templates."""
    data_root = _find_data_root()
    if data_root is None:
        return

    core = data_root / "core"
    _index_agents(conn, core)
    _index_fragments(conn, core)
    _index_skills(conn, core, data_root)
    _index_templates(conn, core, data_root)
