"""Flow stage configuration endpoints."""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

bp = Blueprint("stage_configs", __name__)


def _get_conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


@bp.route("/flows/stage-config", methods=["GET"])
def get_stage_config():
    project_root = request.args.get("project_root", "")
    feature = request.args.get("feature", "")
    stage = request.args.get("stage", "")
    if not (project_root and feature and stage):
        return jsonify({"error": "project_root, feature, stage required"}), 400
    try:
        from pathly_orchestrator.db.queries.stage_configs import read_stage_config

        conn = _get_conn()
        cfg = read_stage_config(conn, project_root, feature, stage)
        return jsonify(cfg or {})
    except Exception as e:
        logging.exception("get_stage_config error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/stage-config", methods=["POST"])
def set_stage_config():
    data = request.get_json() or {}
    project_root = data.get("project_root", "")
    feature = data.get("feature", "")
    stage = data.get("stage", "")
    if not (project_root and feature and stage):
        return jsonify({"error": "project_root, feature, stage required"}), 400
    try:
        from pathly_orchestrator.db.queries.stage_configs import upsert_stage_config

        # flow-phase-inspector (#5): per-stage layer-3 abilities + excluded section headings.
        # Coerce to list-or-None so a malformed body never persists a non-list blob.
        ability_ids = data.get("ability_ids")
        ability_ids = ability_ids if isinstance(ability_ids, list) else None
        excluded_sections = data.get("excluded_sections")
        excluded_sections = (
            excluded_sections if isinstance(excluded_sections, list) else None
        )

        conn = _get_conn()
        upsert_stage_config(
            conn,
            project_root,
            feature,
            stage,
            agent=data.get("agent"),
            adapter=data.get("adapter"),
            skill=data.get("skill"),
            ability_ids=ability_ids,
            excluded_sections=excluded_sections,
        )
        return jsonify({"ok": True})
    except Exception as e:
        logging.exception("set_stage_config error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/stage-config", methods=["DELETE"])
def reset_stage_config():
    data = request.get_json() or {}
    project_root = data.get("project_root", "")
    feature = data.get("feature", "")
    stage = data.get("stage", "")
    if not (project_root and feature and stage):
        return jsonify({"error": "project_root, feature, stage required"}), 400
    try:
        from pathly_orchestrator.db.queries.stage_configs import delete_stage_config

        conn = _get_conn()
        delete_stage_config(conn, project_root, feature, stage)
        return jsonify({"ok": True})
    except Exception as e:
        logging.exception("reset_stage_config error")
        return jsonify({"error": str(e)}), 500
