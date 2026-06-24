"""Per-project fragment-composition overrides (skill_composition table).

The packaged ``composition.yaml`` is the version-controlled default. Rows here are
user/project overrides of a skill's fragment list, merged over the YAML at read time
by :func:`pathly_orchestrator.skills.compose.load_effective_manifest`. Edits from the
skill editor land here instead of rewriting the installed YAML file.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def get_composition_overrides(
    conn: sqlite3.Connection, project_root: str | None = None
) -> dict[str, list]:
    """Return ``{skill_key: fragments_list}`` merging global overrides
    (``project_root IS NULL``) with this project's, where the project-specific row
    wins on a shared key. Malformed rows are skipped, never raised."""
    result: dict[str, list] = {}
    rows = conn.execute(
        "SELECT skill_key, fragments_json FROM skill_composition "
        "WHERE project_root IS NULL OR project_root = ? "
        # NULL (global) first so a project row overwrites it in the dict below.
        "ORDER BY (project_root IS NOT NULL)",
        (project_root,),
    ).fetchall()
    for r in rows:
        try:
            result[r["skill_key"]] = json.loads(r["fragments_json"])
        except (json.JSONDecodeError, TypeError, KeyError):
            continue
    return result


def set_composition_override(
    conn: sqlite3.Connection,
    project_root: str | None,
    skill_key: str,
    fragments: list,
) -> None:
    """Upsert a skill's fragment override (manual upsert — SQLite UNIQUE doesn't span
    NULL ``project_root``)."""
    now = datetime.now(timezone.utc).isoformat()
    payload = json.dumps(list(fragments))
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE skill_composition SET fragments_json=?, updated_at=? "
            "WHERE skill_key=? AND ((project_root IS NULL AND ? IS NULL) OR project_root=?)",
            (payload, now, skill_key, project_root, project_root),
        )
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO skill_composition "
                "(project_root, skill_key, fragments_json, updated_at) VALUES (?, ?, ?, ?)",
                (project_root, skill_key, payload, now),
            )
        conn.commit()


def delete_composition_override(
    conn: sqlite3.Connection, project_root: str | None, skill_key: str
) -> None:
    """Remove a skill's override → revert to the packaged YAML default."""
    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM skill_composition "
            "WHERE skill_key=? AND ((project_root IS NULL AND ? IS NULL) OR project_root=?)",
            (skill_key, project_root, project_root),
        )
        conn.commit()
