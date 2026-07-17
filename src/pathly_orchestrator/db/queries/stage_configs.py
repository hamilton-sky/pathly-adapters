"""Query helpers for the stage_configs table."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def _dump_list(value: list | None) -> str | None:
    """JSON-encode a non-empty list, else NULL (so 'no selection' reads back as [])."""
    return json.dumps(value) if value else None


def _load_list(value) -> list:
    """Parse a JSON-list column, tolerating NULL / malformed as an empty list."""
    if not value:
        return []
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (ValueError, TypeError):
        return []


def upsert_stage_config(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    stage: str,
    agent: str | None = None,
    adapter: str | None = None,
    skill: str | None = None,
    ability_ids: list | None = None,
    excluded_sections: list | None = None,
) -> None:
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO stage_configs (project_root, feature, stage, agent, adapter, skill, "
            "ability_ids, excluded_sections, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(project_root, feature, stage) DO UPDATE SET "
            "agent=excluded.agent, adapter=excluded.adapter, skill=excluded.skill, "
            "ability_ids=excluded.ability_ids, excluded_sections=excluded.excluded_sections, "
            "updated_at=excluded.updated_at",
            (
                project_root,
                feature,
                stage,
                agent or None,
                adapter or None,
                skill or None,
                _dump_list(ability_ids),
                _dump_list(excluded_sections),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def read_stage_config(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    stage: str,
) -> dict | None:
    row = conn.execute(
        "SELECT agent, adapter, skill, ability_ids, excluded_sections "
        "FROM stage_configs WHERE project_root=? AND feature=? AND stage=?",
        (project_root, feature, stage),
    ).fetchone()
    if not row:
        return None
    cfg = dict(row)
    cfg["ability_ids"] = _load_list(cfg.get("ability_ids"))
    cfg["excluded_sections"] = _load_list(cfg.get("excluded_sections"))
    return cfg


def delete_stage_config(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    stage: str,
) -> None:
    with _get_write_lock(conn):
        conn.execute(
            "DELETE FROM stage_configs WHERE project_root=? AND feature=? AND stage=?",
            (project_root, feature, stage),
        )
        conn.commit()
