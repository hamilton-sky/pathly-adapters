"""Query helpers for the stage_configs table."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock


def upsert_stage_config(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    stage: str,
    agent: str | None = None,
    adapter: str | None = None,
    skill: str | None = None,
) -> None:
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO stage_configs (project_root, feature, stage, agent, adapter, skill, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(project_root, feature, stage) DO UPDATE SET "
            "agent=excluded.agent, adapter=excluded.adapter, skill=excluded.skill, updated_at=excluded.updated_at",
            (project_root, feature, stage, agent or None, adapter or None, skill or None,
             datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()


def read_stage_config(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    stage: str,
) -> dict | None:
    row = conn.execute(
        "SELECT agent, adapter, skill FROM stage_configs WHERE project_root=? AND feature=? AND stage=?",
        (project_root, feature, stage),
    ).fetchone()
    return dict(row) if row else None


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
