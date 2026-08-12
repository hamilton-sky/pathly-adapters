"""DB admin endpoints: sandboxed query, settings read/write."""

from __future__ import annotations

import sqlite3

from flask import jsonify, request

from ._db_api_bp import _ALLOWED_KEYWORDS, _FORBIDDEN_KEYWORDS, _get_db, bp, logger


@bp.route("/db/query", methods=["POST"])
def db_query():
    """Sandboxed SELECT-only SQL query."""
    try:
        data = request.get_json() or {}
        sql = str(data.get("sql", "")).strip()
        if not sql:
            return jsonify({"error": "Missing 'sql' field"}), 400
        first_word = sql.lower().split()[0] if sql.split() else ""
        if first_word in _FORBIDDEN_KEYWORDS or first_word not in _ALLOWED_KEYWORDS:
            return jsonify({"error": "Only SELECT queries are allowed"}), 400
        conn = _get_db()
        rows = conn.execute(sql).fetchmany(500)
        return jsonify({"rows": [dict(r) for r in rows]})
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("db_query error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/agents", methods=["GET"])
def db_get_agents():
    """Return the known agent roles from the registry (seeded from core/agents/).

    Powers the Settings model-policy agent list (spawn-policy) so a newly-added agent
    appears automatically instead of being hard-coded. Optional ?project_root= merges
    that project's custom agents over the global set (a project role wins on collision).
    Safe-empty on any error so the UI degrades to its built-in fallback list.
    """
    try:
        from pathly_orchestrator.db.queries.agent_defs import read_agent_definitions

        conn = _get_db()
        merged: dict[str, dict] = {}
        for row in read_agent_definitions(conn, None):
            merged[row["role"]] = row
        project_root = (
            (request.args.get("project_root") or "").strip().replace("\\", "/")
        )
        if project_root:
            for row in read_agent_definitions(conn, project_root):
                merged[row["role"]] = row
        agents = sorted(
            (
                {
                    "role": r["role"],
                    "name": r.get("name") or r["role"],
                    "model": r.get("model") or "",
                    "description": r.get("description") or "",
                }
                for r in merged.values()
            ),
            key=lambda a: a["role"],
        )
        return jsonify({"agents": agents}), 200
    except Exception as e:
        logger.exception("db_get_agents error")
        return jsonify({"agents": []}), 200


@bp.route("/db/settings", methods=["GET"])
def db_get_settings():
    """Return all app_settings."""
    try:
        conn = _get_db()
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        return jsonify({r["key"]: r["value"] for r in rows})
    except Exception as e:
        logger.exception("db_get_settings error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/settings/<key>", methods=["PUT"])
def db_set_setting(key: str):
    """Set an app_setting."""
    try:
        data = request.get_json() or {}
        value = data.get("value")
        if value is None:
            return jsonify({"error": "Missing 'value' field"}), 400
        conn = _get_db()
        conn.execute(
            "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, datetime('now')) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value)),
        )
        conn.commit()
        return jsonify({"status": "ok"})
    except Exception as e:
        logger.exception("db_set_setting error")
        return jsonify({"error": str(e)}), 500
