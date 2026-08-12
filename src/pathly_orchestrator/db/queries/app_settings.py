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


# Keep in sync with _PROJECT_WRITERS / _GLOBAL_WRITERS in
# http_server/blueprints/comms/_helpers.py (the fallback path when no perm_table is passed).
# 'evaluator' is a project+global writer because it only runs human-initiated on the board the
# human opened — see the note there.
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
            "research",
            "evaluator",
            "director",
            "human",
        ]
    ),
    "global": sorted(["director", "evaluator", "human"]),
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
    try:
        raw = get_setting(conn, key)
    except sqlite3.OperationalError:
        # app_settings table absent (a pre-migration connection or a test DB without
        # migrations) — fall back to the built-in defaults rather than 500 the caller
        # (/comms/post reads this on every post). Production always has the table.
        raw = None
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


# ── Spawn policy — per-agent model config (spawn-policy P0) ─────────────
# ONE DB-backed source of truth for "which company + model does each agent use", read by BOTH
# the renderer gate and the Python resolver so nothing re-fragments. Keys:
#   models:default        → {"adapter", "model"}   the global default for every spawn
#   models:role:<role>    → {"adapter", "model"}   an optional per-role/per-place override
# `model` may be "" meaning "use this adapter's own engine default" (resolve_command drops the
# --model pair). Resolution is layered: per-role override → global default → None (engine default).
# Roles ≡ the existing agent/telemetry identities (architect/planner/builder/scout/split/analyze/…).
_MODEL_DEFAULT_KEY = "models:default"
_MODEL_ROLE_PREFIX = "models:role:"


def _model_key(role: str | None) -> str:
    """The app_settings key for a role's model, or the global default for ''/'default'/None."""
    return (
        _MODEL_DEFAULT_KEY
        if role in ("", "default", None)
        else f"{_MODEL_ROLE_PREFIX}{role}"
    )


def _coerce_model_policy(raw: str | None) -> dict | None:
    """Parse a stored {"adapter","model"} value, or None when absent/malformed (→ engine default)."""
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict):
        return None
    adapter = parsed.get("adapter")
    if not isinstance(adapter, str) or not adapter.strip():
        return None
    model = parsed.get("model")
    model = model.strip() if isinstance(model, str) else ""
    return {"adapter": adapter.strip(), "model": model}


def resolve_agent_model(conn: sqlite3.Connection, role: str) -> dict | None:
    """Resolve the effective {"adapter","model"} for a role: per-role override → global default
    → None (caller keeps its adapter and lets the engine pick its own default model).

    Returns None (never raises) whenever nothing is configured or a value is malformed, so a
    spawn always degrades to today's behavior rather than failing.
    """
    try:
        override = _coerce_model_policy(get_setting(conn, _model_key(role)))
        if override is not None:
            return override
        return _coerce_model_policy(get_setting(conn, _MODEL_DEFAULT_KEY))
    except sqlite3.OperationalError:
        # app_settings absent (pre-migration / bare test DB) — degrade, never 500 a spawn.
        return None


def set_agent_model(
    conn: sqlite3.Connection, role: str | None, adapter: str, model: str = ""
) -> None:
    """Set the global default (role in ''/'default'/None) or a per-role override. `model` may be
    empty (= that adapter's engine default). Raises ValueError on a blank adapter."""
    if not isinstance(adapter, str) or not adapter.strip():
        raise ValueError("adapter must be a non-empty string")
    if not isinstance(model, str):
        raise ValueError("model must be a string (may be empty for the engine default)")
    payload = {"adapter": adapter.strip(), "model": model.strip()}
    set_setting(conn, _model_key(role), json.dumps(payload))


def clear_agent_model(conn: sqlite3.Connection, role: str | None) -> None:
    """Remove a per-role override (falls back to the global default), or clear the global default."""
    key = _model_key(role)
    with _get_write_lock(conn):
        conn.execute("DELETE FROM app_settings WHERE key=?", (key,))
        conn.commit()


def get_model_policy(conn: sqlite3.Connection) -> dict:
    """The full policy for the Settings UI: {"default": {...}|None, "roles": {role: {...}}}."""
    default: dict | None = None
    roles: dict[str, dict] = {}
    try:
        alls = get_all_settings(conn)
    except sqlite3.OperationalError:
        return {"default": None, "roles": {}}
    for key, val in alls.items():
        if key == _MODEL_DEFAULT_KEY:
            default = _coerce_model_policy(val)
        elif key.startswith(_MODEL_ROLE_PREFIX):
            coerced = _coerce_model_policy(val)
            if coerced is not None:
                roles[key[len(_MODEL_ROLE_PREFIX) :]] = coerced
    return {"default": default, "roles": roles}


# ── Spawn policy — logging destinations (spawn-policy P0) ───────────────
# Controls the AGENT-NARRATION sinks only. The cost/monitor spine (run_history, agent_invocations,
# completion-report, gate liveness) is the control plane itself and is ALWAYS ON — it is
# deliberately NOT represented here, so it can never be switched off.
_LOGGING_BOARD_KEY = "logging:board_enabled"


def get_logging_config(conn: sqlite3.Connection) -> dict:
    """Return {"board": bool, "verbosity": 'quiet'|'normal'|'verbose'}. Board narration defaults ON;
    verbosity reuses the existing board:default_progress setting (single source of truth).
    """
    try:
        raw = get_setting(conn, _LOGGING_BOARD_KEY)
    except sqlite3.OperationalError:
        raw = None
    board_enabled = True if raw is None else (raw == "true")
    return {"board": board_enabled, "verbosity": get_default_progress(conn) or "normal"}


def set_logging_board_enabled(conn: sqlite3.Connection, enabled: bool) -> None:
    """Turn agent BOARD narration on/off. Does NOT touch the always-on cost/monitor spine."""
    set_setting(conn, _LOGGING_BOARD_KEY, "true" if enabled else "false")
