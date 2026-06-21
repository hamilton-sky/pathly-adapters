"""Query helpers for the app_settings table."""

from __future__ import annotations

import json
import os
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


def get_setting(
    conn: sqlite3.Connection, key: str, default: str | None = None
) -> str | None:
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


_DEFAULT_WRITE_PERMISSIONS: dict[str, list[str]] = {
    "feature": ["*"],
    "project": sorted(
        [
            "tester",
            "reviewer",
            "explorer",
            "architect",
            "planner",
            "designer",
            "director",
            "human",
        ]
    ),
    "global": sorted(["director", "human"]),
}


def get_write_permissions(
    conn: sqlite3.Connection,
    project_root: str,
) -> dict:
    """Return the resolved write-permission table merged with any project overrides.

    Returns a dict with keys 'feature', 'project', 'global' each mapping to a
    list of allowed roles (or ['*'] for unrestricted). Project-level overrides
    are merged onto the default table.
    """
    key = f"write_permissions:{project_root}"
    raw = get_setting(conn, key)
    result = {k: list(v) for k, v in _DEFAULT_WRITE_PERMISSIONS.items()}
    if raw is not None:
        try:
            overrides = json.loads(raw)
            if isinstance(overrides, dict):
                for tier, roles in overrides.items():
                    if tier in result and isinstance(roles, list):
                        result[tier] = roles
        except (json.JSONDecodeError, TypeError):
            pass
    return result


def set_write_permissions(
    conn: sqlite3.Connection,
    project_root: str,
    overrides: dict,
) -> None:
    """Persist project-level write-permission overrides in app_settings."""
    key = f"write_permissions:{project_root}"
    set_setting(conn, key, json.dumps(overrides))


_INFERENCE_BACKEND_KEY = "inference:summary_backend"
_VALID_BACKENDS = {"minilm", "ollama", "haiku"}


def get_summary_backend(conn: sqlite3.Connection) -> str:
    """Return the active summary backend.

    Precedence: app_settings row > PATHLY_SUMMARY_BACKEND env var > "minilm".
    Always returns a member of {"minilm", "ollama", "haiku"}.
    """
    raw = get_setting(conn, _INFERENCE_BACKEND_KEY)
    if raw in _VALID_BACKENDS:
        return raw
    env = os.environ.get("PATHLY_SUMMARY_BACKEND")
    if env in _VALID_BACKENDS:
        return env
    return "minilm"


def set_summary_backend(conn: sqlite3.Connection, backend: str) -> None:
    """Persist the summary backend choice. Raises ValueError on invalid value."""
    if backend not in _VALID_BACKENDS:
        raise ValueError(
            f"Invalid summary backend {backend!r}. Must be one of: {sorted(_VALID_BACKENDS)}"
        )
    set_setting(conn, _INFERENCE_BACKEND_KEY, backend)
