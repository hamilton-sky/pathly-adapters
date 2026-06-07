"""Read the fragment catalog for the skill notebook editor."""

from __future__ import annotations

import os
import re


def read_fragment_catalog(core_skills_dir: str) -> list[dict]:
    """Scan core_skills_dir/fragments/ and return fragment metadata.

    Parses YAML frontmatter (name, description, category, requires) from each .md
    file when present.  Falls back to filename-derived name when frontmatter is absent.

    Returns list of:
      {"name": str, "description": str, "category": str, "requires": str | None}
    """
    fragments_dir = os.path.join(core_skills_dir, "fragments")
    catalog: list[dict] = []

    if not os.path.isdir(fragments_dir):
        return catalog

    for filename in sorted(os.listdir(fragments_dir)):
        if not filename.endswith(".md"):
            continue

        filepath = os.path.join(fragments_dir, filename)
        basename = filename[:-3]  # strip .md

        with open(filepath, encoding="utf-8") as f:
            text = f.read()

        name, description, category, requires = _parse_frontmatter(text, basename)
        catalog.append({
            "name": name,
            "description": description,
            "category": category,
            "requires": requires,
        })

    return catalog


def _parse_frontmatter(text: str, fallback_name: str) -> tuple[str, str, str, str | None]:
    """Extract (name, description, category, requires) from YAML frontmatter.

    Returns fallback_name for name and empty strings for other fields when no
    frontmatter is present.  Only parses simple key: value lines (no nested YAML).
    """
    name = fallback_name
    description = ""
    category = ""
    requires: str | None = None

    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return name, description, category, requires

    frontmatter = match.group(1)
    for line in frontmatter.splitlines():
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
