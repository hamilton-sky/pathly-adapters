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
        (norm, norm.replace("/", "\\")),
    ).fetchone()
    return dict(row) if row else None


# ── indexer ──────────────────────────────────────────────────────────────────


def move_catalog_item(
    conn: sqlite3.Connection,
    item_type: str,
    name: str,
    new_category: str,
) -> dict:
    """Move a catalog item to a different category directory.

    Returns a dict with updated name/category/abs_path/rel_path fields.
    """
    import shutil as _shutil

    row = conn.execute(
        "SELECT * FROM catalog_items WHERE item_type=? AND name=?", (item_type, name)
    ).fetchone()
    if not row:
        raise ValueError(f"Item '{name}' of type '{item_type}' not found")
    row = dict(row)

    old_abs_path = Path(row["abs_path"].replace("/", os.sep))
    data_root = _find_data_root()
    if not data_root:
        raise RuntimeError("Cannot locate pathly_data")

    core = data_root / "core"
    type_to_base: dict[str, Path] = {
        "skill": core / "skills",
        "agent": core / "agents",
        "fragment": core / "skills" / "fragments",
        "template": core / "templates",
    }
    base = type_to_base.get(item_type, core / "skills")
    new_dir = base / new_category if new_category else base
    new_dir.mkdir(parents=True, exist_ok=True)

    new_abs_path = new_dir / old_abs_path.name
    if old_abs_path.resolve() == new_abs_path.resolve():
        return row  # already in target category

    if new_abs_path.exists():
        raise FileExistsError(
            f"An item named '{old_abs_path.name}' already exists in "
            f"'{new_category or 'Uncategorized'}'"
        )

    _shutil.move(str(old_abs_path), str(new_abs_path))

    stem = old_abs_path.stem
    if item_type in ("skill", "template", "fragment"):
        new_name = f"{new_category}/{stem}" if new_category else stem
    else:
        new_name = stem

    new_abs_str = str(new_abs_path).replace("\\", "/")
    new_rel = _rel(new_abs_path, data_root.parent)

    with _get_write_lock(conn):
        conn.execute(
            "UPDATE catalog_items SET name=?, category=?, abs_path=?, rel_path=? "
            "WHERE item_type=? AND name=?",
            (new_name, new_category, new_abs_str, new_rel, item_type, name),
        )
        conn.commit()

    return {
        "name": new_name,
        "category": new_category,
        "abs_path": new_abs_str,
        "rel_path": new_rel,
    }


def rename_catalog_item(
    conn: sqlite3.Connection,
    item_type: str,
    name: str,
    new_stem: str,
) -> dict:
    """Rename a catalog item file (same directory, new filename stem).

    Returns updated fields: {name, abs_path, rel_path}
    """
    import re as _re

    row = conn.execute(
        "SELECT * FROM catalog_items WHERE item_type=? AND name=?", (item_type, name)
    ).fetchone()
    if not row:
        raise ValueError(f"Item '{name}' of type '{item_type}' not found")
    row = dict(row)

    safe_stem = _re.sub(r"[^a-z0-9\-_]", "-", new_stem.lower()).strip("-")
    if not safe_stem:
        raise ValueError("Invalid name")

    old_abs = Path(row["abs_path"].replace("/", os.sep))
    new_abs = old_abs.parent / f"{safe_stem}{old_abs.suffix}"

    if old_abs.resolve() == new_abs.resolve():
        return row
    if new_abs.exists():
        raise FileExistsError(f"'{safe_stem}' already exists in this category")

    old_abs.rename(new_abs)

    data_root = _find_data_root()
    category = row.get("category", "")
    if item_type in ("skill", "template", "fragment"):
        new_name = (
            f"{category}/{safe_stem}"
            if category and category not in (item_type, "fragments")
            else safe_stem
        )
    else:
        new_name = safe_stem

    new_abs_str = str(new_abs).replace("\\", "/")
    new_rel = _rel(new_abs, data_root.parent) if data_root else new_abs_str

    with _get_write_lock(conn):
        conn.execute(
            "UPDATE catalog_items SET name=?, abs_path=?, rel_path=? WHERE item_type=? AND name=?",
            (new_name, new_abs_str, new_rel, item_type, name),
        )
        conn.commit()

    return {"name": new_name, "abs_path": new_abs_str, "rel_path": new_rel}


def rename_catalog_category(
    conn: sqlite3.Connection,
    item_type: str,
    old_name: str,
    new_name: str,
) -> dict:
    """Rename a catalog category directory and update all items in it.

    Returns {oldName, newName, updatedItems}
    """
    import re as _re
    import shutil as _shutil

    safe_new = _re.sub(r"[^a-z0-9\-_]", "-", new_name.lower()).strip("-")
    if not safe_new:
        raise ValueError("Invalid category name")

    data_root = _find_data_root()
    if not data_root:
        raise RuntimeError("Cannot locate pathly_data")

    core = data_root / "core"
    type_to_base: dict[str, Path] = {
        "skill": core / "skills",
        "agent": core / "agents",
        "fragment": core / "skills" / "fragments",
        "template": core / "templates",
    }
    base = type_to_base.get(item_type, core / "skills")
    old_dir = base / old_name
    new_dir = base / safe_new

    if not old_dir.exists():
        raise ValueError(f"Category '{old_name}' not found on disk")
    if new_dir.exists():
        raise FileExistsError(f"Category '{safe_new}' already exists")

    _shutil.move(str(old_dir), str(new_dir))

    rows = conn.execute(
        "SELECT name, abs_path FROM catalog_items WHERE item_type=? AND category=?",
        (item_type, old_name),
    ).fetchall()

    with _get_write_lock(conn):
        for r in rows:
            r = dict(r)
            old_item_abs = Path(r["abs_path"].replace("/", os.sep))
            new_item_abs = new_dir / old_item_abs.name
            stem = old_item_abs.stem
            if item_type in ("skill", "template", "fragment"):
                new_item_name = f"{safe_new}/{stem}"
            else:
                new_item_name = stem
            conn.execute(
                "UPDATE catalog_items SET name=?, category=?, abs_path=?, rel_path=? "
                "WHERE item_type=? AND name=?",
                (
                    new_item_name,
                    safe_new,
                    str(new_item_abs).replace("\\", "/"),
                    _rel(new_item_abs, data_root.parent),
                    item_type,
                    r["name"],
                ),
            )
        conn.commit()

    return {"oldName": old_name, "newName": safe_new, "updatedItems": len(rows)}


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


def _index_fragments(conn: sqlite3.Connection, core: Path) -> None:
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
                text = text[end + 4 :]
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
