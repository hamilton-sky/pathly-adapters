"""DB explorer per-feature detail routes: events, agents, otel spans, run history.

Split out of db_api_explorer.py (SRP 400-line cap) — routes moved verbatim.
"""

from __future__ import annotations

import json

from flask import jsonify

from ._db_api_bp import _get_db, _project_root_param, bp, logger


@bp.route("/db/features/<feature>/events", methods=["GET"])
def db_feature_events(feature: str):
    """Events for a specific feature."""
    try:
        conn = _get_db()
        pr = _project_root_param()
        query = "SELECT seq, ts, event_type, payload FROM fsm_events WHERE feature=?"
        params: list = [feature]
        if pr:
            query += " AND project_root=?"
            params.append(pr)
        query += " ORDER BY seq DESC LIMIT 200"
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            try:
                payload = json.loads(r["payload"])
            except (json.JSONDecodeError, TypeError):
                payload = {}
            results.append(
                {
                    "seq": r["seq"],
                    "ts": r["ts"],
                    "event_type": r["event_type"],
                    "payload": payload,
                }
            )
        return jsonify(results)
    except Exception as e:
        logger.exception("db_feature_events error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/features/<feature>/agents", methods=["GET"])
def db_feature_agents(feature: str):
    """Agent invocations for a specific feature."""
    try:
        conn = _get_db()
        pr = _project_root_param()
        # run-identity: match the slug OR the spawn-issued board_scope, so a goal
        # run's invocations surface under its parent feature too. Legacy rows (NULL
        # board_scope) behave exactly as before.
        query = (
            "SELECT id, run_id, stage, agent_role, started_at, finished_at, "
            "tokens_in, tokens_out, cost_usd, session_id, summary, scope_tier, "
            "board_scope "
            "FROM agent_invocations WHERE (feature=? OR board_scope=?)"
        )
        params: list = [feature, feature]
        if pr:
            query += " AND project_root=?"
            params.append(pr)
        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.exception("db_feature_agents error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/features/<feature>/otel", methods=["GET"])
def db_feature_otel(feature: str):
    """OTel spans for a specific feature."""
    try:
        conn = _get_db()
        pr = _project_root_param()
        query = (
            "SELECT id, trace_id, span_id, parent_span_id, name, "
            "start_time, end_time, attributes, scope_tier "
            "FROM otel_spans WHERE feature=?"
        )
        params: list = [feature]
        if pr:
            query += " AND project_root=?"
            params.append(pr)
        query += " ORDER BY id DESC LIMIT 200"
        rows = conn.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            try:
                d["attributes"] = json.loads(d["attributes"] or "{}")
            except (json.JSONDecodeError, TypeError):
                d["attributes"] = {}
            results.append(d)
        return jsonify(results)
    except Exception as e:
        logger.exception("db_feature_otel error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/features/<feature>/runs", methods=["GET"])
def db_feature_runs(feature: str):
    """Run history for a specific feature."""
    try:
        conn = _get_db()
        pr = _project_root_param()
        # run-identity: slug OR board_scope (goal runs under their parent feature),
        # plus the legacy basename shim (rows written before the slug keying fix hold
        # the full topic path — matched by '/'-suffix, never rewritten).
        query = (
            "SELECT id, run_id, status, started_at, finished_at, "
            "stage_count, total_tokens, cost_usd, adapter, board_scope "
            "FROM run_history "
            "WHERE (feature=? OR board_scope=? OR feature LIKE '%/' || ?)"
        )
        params: list = [feature, feature, feature]
        if pr:
            query += " AND project_root=?"
            params.append(pr)
        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.exception("db_feature_runs error")
        return jsonify({"error": str(e)}), 500
