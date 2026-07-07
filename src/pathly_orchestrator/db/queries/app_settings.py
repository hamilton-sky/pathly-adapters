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
            "builder",
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


# unified-ai-routing (Conv 3): app-default AI target for artifact summarization.
# JSON-encoded AiSelection {"type":"model"|"engine","id":...}. The summarizer is
# CLIENT-side — the renderer runs aiRouter against this target.
_DEFAULT_SUMMARY_SELECTION_KEY = "ai_routing:default_summary_selection"


def get_default_summary_selection(conn: sqlite3.Connection) -> dict | None:
    """Return the app-default summary AiSelection ({"type","id"}), or None if unset.

    A malformed stored value degrades to None so the client falls back to its
    built-in default rather than crashing.
    """
    raw = get_setting(conn, _DEFAULT_SUMMARY_SELECTION_KEY)
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if (
        isinstance(parsed, dict)
        and parsed.get("type") in ("model", "engine")
        and isinstance(parsed.get("id"), str)
    ):
        return {"type": parsed["type"], "id": parsed["id"]}
    return None


def set_default_summary_selection(conn: sqlite3.Connection, selection: dict) -> None:
    """Persist the app-default summary AiSelection. Raises ValueError if malformed."""
    if (
        not isinstance(selection, dict)
        or selection.get("type") not in ("model", "engine")
        or not isinstance(selection.get("id"), str)
        or not selection["id"].strip()
    ):
        raise ValueError(
            "selection must be {'type': 'model'|'engine', 'id': <non-empty str>}"
        )
    payload = {"type": selection["type"], "id": selection["id"]}
    set_setting(conn, _DEFAULT_SUMMARY_SELECTION_KEY, json.dumps(payload))


_DEFAULT_SUMMARY_STYLE_KEY = "ai_routing:default_summary_style"
_VALID_SUMMARY_STYLES = ("gist", "topic-map", "detailed")


def get_default_summary_style(conn: sqlite3.Connection) -> str | None:
    """Return the app-default summary DEPTH style ('gist'|'topic-map'|'detailed'), or None.

    A missing or unrecognised value degrades to None so the client falls back to its
    built-in default (topic-map)."""
    raw = get_setting(conn, _DEFAULT_SUMMARY_STYLE_KEY)
    return raw if raw in _VALID_SUMMARY_STYLES else None


def set_default_summary_style(conn: sqlite3.Connection, style: str) -> None:
    """Persist the app-default summary DEPTH style. Raises ValueError if invalid."""
    if style not in _VALID_SUMMARY_STYLES:
        raise ValueError("style must be one of 'gist', 'topic-map', 'detailed'")
    set_setting(conn, _DEFAULT_SUMMARY_STYLE_KEY, style)


_DEFAULT_PROGRESS_KEY = "board:default_progress"
_VALID_PROGRESS = ("quiet", "normal", "verbose")


def get_default_progress(conn: sqlite3.Connection) -> str | None:
    """Return the app-default board-updates verbosity ('quiet'|'normal'|'verbose'), or None.

    This is the single source of truth for how chatty a headless agent is on the board.
    Every board-narrating run (single-agent, evaluator, decompose, single-executor) resolves
    its cadence from here when the caller doesn't pass an explicit override. A missing or
    unrecognised value degrades to None so the consumer falls back to its built-in 'normal'.
    """
    raw = get_setting(conn, _DEFAULT_PROGRESS_KEY)
    return raw if raw in _VALID_PROGRESS else None


def set_default_progress(conn: sqlite3.Connection, progress: str) -> None:
    """Persist the app-default board-updates verbosity. Raises ValueError if invalid."""
    if progress not in _VALID_PROGRESS:
        raise ValueError("progress must be one of 'quiet', 'normal', 'verbose'")
    set_setting(conn, _DEFAULT_PROGRESS_KEY, progress)
