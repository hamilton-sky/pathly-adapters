"""Query helpers for the app_settings table."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from ..connection import _get_write_lock

_BOARD_SCOPE_DEFAULT = {"feature": True, "project": True, "global": True}


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    """Upsert a setting."""
    now = datetime.now(timezone.utc).isoformat()
    with _get_write_lock(conn):
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, value, now),
        )
        conn.commit()


def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    """Return setting value or default."""
    row = conn.execute("SELECT value FROM app_settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def get_all_settings(conn: sqlite3.Connection) -> dict[str, str]:
    """Return all settings as a dict."""
    rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
    return {r["key"]: r["value"] for r in rows}


def get_board_scope(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
) -> dict[str, bool]:
    """Return board_scope for a feature, defaulting to all-enabled when absent."""
    key = f"board_scope:{project_root}:{feature}"
    raw = get_setting(conn, key)
    if raw is None:
        return dict(_BOARD_SCOPE_DEFAULT)
    try:
        parsed = json.loads(raw)
        result = dict(_BOARD_SCOPE_DEFAULT)
        result.update({k: bool(v) for k, v in parsed.items() if k in result})
        return result
    except (json.JSONDecodeError, TypeError, AttributeError):
        return dict(_BOARD_SCOPE_DEFAULT)


def set_board_scope(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    scope_dict: dict[str, bool],
) -> None:
    """Persist board_scope for a feature as JSON in app_settings."""
    key = f"board_scope:{project_root}:{feature}"
    set_setting(conn, key, json.dumps(scope_dict))
