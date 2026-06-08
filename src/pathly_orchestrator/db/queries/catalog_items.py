"""Query helpers for the catalog_items table."""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from ..connection import _get_write_lock


# ── public write/read ────────────────────────────────────────────────────────

def upsert_catalog_item(
    conn: sqlite3.Connection,
    item_type: str,
    name: str,
    rel_path: str,
    abs_path: str,
    category: str,
    description: str,
    tags: str = "",
    content: str = "",
) -> int:
    """Upsert a catalog item. Returns the row id."""
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT OR REPLACE INTO catalog_items "
            "(item_type, name, rel_path, abs_path, category, description, tags, content, indexed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item_type,
                name,
                rel_path,
                abs_path,
                category,
                description,
                tags,
                content,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def read_all_catalog_items(conn: sqlite3.Connection) -> list[dict]:
    """Return all catalog items ordered by type then name."""
    rows = conn.execute(
        "SELECT * FROM catalog_items ORDER BY item_type, name"
    ).fetchall()
    return [dict(r) for r in rows]


def read_catalog_item_by_path(conn: sqlite3.Connection, abs_path: str) -> dict | None:
    """Return a catalog item by its absolute path, or None if not found."""
    norm = abs_path.replace("\\", "/")
    row = conn.execute(
        "SELECT * FROM catalog_items WHERE abs_path=? OR abs_path=?",
        (norm, norm.replace("/", "\\"))
    ).fetchone()
    return dict(row) if row else None


# ── indexer ──────────────────────────────────────────────────────────────────

def rebuild_catalog(conn: sqlite3.Connection) -> None:
    """Walk pathly_data/core and (re)index agents, fragments, skills, templates.

    Uses INSERT OR REPLACE so re-runs are fully idempotent.
    """
    data_root = _find_data_root()
    if data_root is None:
        return

    core = data_root / "core"
    _index_agents(conn, core)
    _index_fragments(conn, core)
    _index_skills(conn, core, data_root)
    _index_templates(conn, core, data_root)


# ── private helpers ───────────────────────────────────────────────────────────

def _find_data_root() -> Path | None:
    """Locate the pathly_data package root by walking up from this file."""
    this_dir = Path(__file__).resolve().parent
    for parent in [
        this_dir.parent,
        this_dir.parent.parent,
        this_dir.parent.parent.parent,
        this_dir.parent.parent.parent.parent,
    ]:
        candidate = parent / "pathly_data" / "core"
        if candidate.exists():
            return parent / "pathly_data"
    # Fallback: importlib.resources
    try:
        from importlib.resources import files as _res_files
        p = Path(str(_res_files("pathly_data").joinpath("core")))
        if p.exists():
            return p.parent
    except Exception:
        pass
    return None


def _index_agents(conn: sqlite3.Connection, core: Path) -> None:
    agents_dir = core / "agents"
    if not agents_dir.exists():
        return
    for f in sorted(agents_dir.glob("*.md")):
        if "README" in f.name:
            continue
        content = f.read_text(encoding="utf-8")
        upsert_catalog_item(
            conn,
            item_type="agent",
            name=f.stem,
            rel_path=_rel(f, core.parent.parent),
            abs_path=str(f).replace("\\", "/"),
            category="agents",
            description=_first_line(f),
            content=content,
        )


def _index_fragments(conn: sqlite3.Connection, core: Path) -> None:
    fragments_dir = core / "skills" / "fragments"
    if not fragments_dir.exists():
        return
    for f in sorted(fragments_dir.glob("*.md")):
        content = f.read_text(encoding="utf-8")
        name, description, category, _ = _parse_frontmatter(content, f.stem)
        upsert_catalog_item(
            conn,
            item_type="fragment",
            name=name,
            rel_path=_rel(f, core.parent.parent),
            abs_path=str(f).replace("\\", "/"),
            category=category or "fragments",
            description=description,
            content=content,
        )


def _index_skills(conn: sqlite3.Connection, core: Path, _data_root: Path) -> None:
    skills_dir = core / "skills"
    if not skills_dir.exists():
        return
    for f in sorted(skills_dir.rglob("*.md")):
        parts = f.relative_to(skills_dir).parts
        # Skip fragments/ subdirectory — handled separately
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


def _index_templates(conn: sqlite3.Connection, core: Path, _data_root: Path) -> None:
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


def _rel(path: Path, base: Path) -> str:
    """Return path relative to base, with forward slashes."""
    try:
        return str(path.relative_to(base)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _first_line(path: Path) -> str:
    """Return the first non-heading, non-blank line as a short description."""
    try:
        text = path.read_text(encoding="utf-8")
        # Skip YAML frontmatter
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


def _parse_frontmatter(text: str, fallback_name: str) -> tuple[str, str, str, str | None]:
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
