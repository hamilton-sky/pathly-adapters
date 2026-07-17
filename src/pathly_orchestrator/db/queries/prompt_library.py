"""prompt_library — the ONE store behind every prompt dropdown + the ability packs.

Rows are user-authored (``source='user'``) or seeded builtins (``source='builtin'``).
Two kinds share the table:

  * ``kind='preset'``  → single-select alternatives (analyze/diagram/eval/system dropdowns)
  * ``kind='ability'`` → additive, stackable layer-3 modifiers (domain/approach packs)

``project_root IS NULL`` is a GLOBAL row; a project row overrides a global one on the same
``(kind, category, name)``. Every function takes an open ``conn`` (mirrors
``skill_composition.py``) so it unit-tests against a temp DB without the ``get_db``
machinery; blueprint handlers pass ``get_db(project_root)``.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from ..connection import _get_write_lock

_FIELDS = (
    "id",
    "project_root",
    "kind",
    "category",
    "name",
    "label",
    "hint",
    "body",
    "skill_ref",
    "source",
    "sort_order",
    "created_at",
    "updated_at",
)

_UPDATABLE = ("label", "hint", "body", "skill_ref", "sort_order")


def _norm_root(project_root: str | None) -> str | None:
    """Canonicalize a project root so editor writes (forward slashes) and runtime reads
    (OS-native) resolve to the same DB key. Mirrors skill_composition._norm_root."""
    if not project_root:
        return None
    return project_root.replace("\\", "/").rstrip("/") or None


def _row_to_dict(r: sqlite3.Row) -> dict:
    return {k: r[k] for k in _FIELDS}


def _new_id() -> str:
    return "pl_" + uuid.uuid4().hex[:12]


def list_prompts(
    conn: sqlite3.Connection,
    *,
    kind: str | None = None,
    category: str | None = None,
    project_root: str | None = None,
) -> list[dict]:
    """Return prompts merging GLOBAL rows with this project's, the project row winning on
    a shared ``(kind, category, name)``. Optionally filtered by ``kind``/``category``.
    Ordered by ``sort_order`` then ``created_at``."""
    project_root = _norm_root(project_root)
    where = ["(project_root IS NULL OR project_root = ?)"]
    params: list = [project_root]
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if category:
        where.append("category = ?")
        params.append(category)
    rows = conn.execute(
        f"SELECT {', '.join(_FIELDS)} FROM prompt_library "
        f"WHERE {' AND '.join(where)} "
        # NULL (global) first so a project row overwrites it in the merge below.
        "ORDER BY (project_root IS NOT NULL), sort_order, created_at",
        params,
    ).fetchall()
    merged: dict[tuple, dict] = {}
    for r in rows:
        d = _row_to_dict(r)
        merged[(d["kind"], d["category"], d["name"])] = d
    return list(merged.values())


def get_prompt(conn: sqlite3.Connection, prompt_id: str) -> dict | None:
    r = conn.execute(
        f"SELECT {', '.join(_FIELDS)} FROM prompt_library WHERE id = ?",
        (prompt_id,),
    ).fetchone()
    return _row_to_dict(r) if r else None


def create_prompt(
    conn: sqlite3.Connection,
    *,
    kind: str,
    category: str,
    name: str,
    label: str,
    body: str,
    hint: str = "",
    skill_ref: str | None = None,
    project_root: str | None = None,
    source: str = "user",
    sort_order: int = 0,
    prompt_id: str | None = None,
) -> dict:
    """Insert a prompt, or REPLACE the one with the same ``(kind, category, name, scope)``
    — ``name`` is the natural key within a scope (the UNIQUE index enforces it), so a
    re-add with the same name edits in place instead of erroring. Returns the stored row.
    """
    project_root = _norm_root(project_root)
    pid = prompt_id or _new_id()
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE prompt_library SET label=?, hint=?, body=?, skill_ref=?, "
            "source=?, sort_order=?, updated_at=? "
            "WHERE kind=? AND category=? AND name=? "
            "AND ((project_root IS NULL AND ? IS NULL) OR project_root=?)",
            (
                label,
                hint,
                body,
                skill_ref,
                source,
                sort_order,
                now,
                kind,
                category,
                name,
                project_root,
                project_root,
            ),
        )
        if cur.rowcount == 0:
            conn.execute(
                f"INSERT INTO prompt_library ({', '.join(_FIELDS)}) "
                f"VALUES ({', '.join(['?'] * len(_FIELDS))})",
                (
                    pid,
                    project_root,
                    kind,
                    category,
                    name,
                    label,
                    hint,
                    body,
                    skill_ref,
                    source,
                    sort_order,
                    now,
                    now,
                ),
            )
        conn.commit()
    row = conn.execute(
        f"SELECT {', '.join(_FIELDS)} FROM prompt_library "
        "WHERE kind=? AND category=? AND name=? "
        "AND ((project_root IS NULL AND ? IS NULL) OR project_root=?)",
        (kind, category, name, project_root, project_root),
    ).fetchone()
    return _row_to_dict(row)


def update_prompt(
    conn: sqlite3.Connection, prompt_id: str, fields: dict
) -> dict | None:
    """Patch an existing prompt by id. ``fields`` may carry any of label/hint/body/
    skill_ref/sort_order; a key's PRESENCE means "set" (a null clears it), absence
    leaves it unchanged. Returns the updated row, or None if ``prompt_id`` is unknown.
    """
    existing = get_prompt(conn, prompt_id)
    if existing is None:
        return None
    merged = {k: existing[k] for k in _UPDATABLE}
    for k in _UPDATABLE:
        if k in fields:
            merged[k] = fields[k]
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "UPDATE prompt_library SET label=?, hint=?, body=?, skill_ref=?, "
            "sort_order=?, updated_at=? WHERE id=?",
            (
                merged["label"],
                merged["hint"],
                merged["body"],
                merged["skill_ref"],
                merged["sort_order"],
                now,
                prompt_id,
            ),
        )
        conn.commit()
    return get_prompt(conn, prompt_id)


def delete_prompt(conn: sqlite3.Connection, prompt_id: str) -> bool:
    """Remove a prompt by id. Returns True if a row was deleted."""
    with _get_write_lock(conn):
        cur = conn.execute("DELETE FROM prompt_library WHERE id=?", (prompt_id,))
        conn.commit()
    return cur.rowcount > 0


def seed_builtins(conn: sqlite3.Connection, rows: list[dict]) -> int:
    """Idempotently seed GLOBAL builtin rows (``source='builtin'``). Each row needs
    kind/category/name/label/body (+ optional hint/skill_ref/sort_order). A row whose
    ``(kind, category, name)`` already exists at global scope is left untouched, so a
    user edit to a seeded prompt is never clobbered on the next boot. Returns the count
    of NEW rows inserted."""
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        for row in rows:
            exists = conn.execute(
                "SELECT 1 FROM prompt_library "
                "WHERE kind=? AND category=? AND name=? AND project_root IS NULL",
                (row["kind"], row["category"], row["name"]),
            ).fetchone()
            if exists:
                continue
            conn.execute(
                f"INSERT INTO prompt_library ({', '.join(_FIELDS)}) "
                f"VALUES ({', '.join(['?'] * len(_FIELDS))})",
                (
                    _new_id(),
                    None,
                    row["kind"],
                    row["category"],
                    row["name"],
                    row["label"],
                    row.get("hint", ""),
                    row["body"],
                    row.get("skill_ref"),
                    "builtin",
                    row.get("sort_order", 0),
                    now,
                    now,
                ),
            )
            inserted += 1
        conn.commit()
    return inserted
