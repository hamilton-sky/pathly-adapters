"""DB explorer endpoints: stats, features, per-feature sub-resources, trends."""

from __future__ import annotations

import json
from pathlib import Path

from flask import jsonify, request

from ._db_api_bp import _get_db, _project_root_param, bp, logger


def _parse_json_file(path: Path) -> dict:
    """Read a JSON file that may have YAML frontmatter (--- ... --- {json})."""
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("---"):
        parts = [p.strip() for p in raw.split("---") if p.strip()]
        raw = parts[-1] if parts else "{}"
    return json.loads(raw)


def _scan_filesystem_features(project_root: str) -> list[dict]:
    """Scan pathly/plans/*/STATE.json for features not yet in the DB."""
    results: list[dict] = []
    plans_dir = Path(project_root) / "pathly" / "plans"
    if not plans_dir.is_dir():
        return results

    for state_file in sorted(plans_dir.glob("*/STATE.json")):
        feature_name = state_file.parent.name
        try:
            state = _parse_json_file(state_file)
        except Exception:
            continue

        current = state.get("current", "UNKNOWN").upper()
        updated_at = state.get("updated_at", "")
        convs_done = int(state.get("convs_done", 0))
        convs_total = int(state.get("convs_total", 0))

        cost_usd = 0.0
        runner_file = state_file.parent / "RUNNER_STATE.json"
        if runner_file.exists():
            try:
                runner = _parse_json_file(runner_file)
                cost_usd = float(runner.get("cost_usd_so_far", 0.0))
            except Exception:
                pass

        results.append(
            {
                "project_root": project_root,
                "feature": feature_name,
                "state": current,
                "events": 0,
                "invocations": 0,
                "total_tokens": 0,
                "cost_usd": cost_usd,
                "updated_at": updated_at,
                "convs_done": convs_done,
                "convs_total": convs_total,
                "source": "filesystem",
            }
        )
    return results


@bp.route("/db/stats", methods=["GET"])
def db_stats():
    """Aggregate counts — DB + filesystem feature count."""
    try:
        project_root = _project_root_param()
        conn = _get_db()

        db_features_count = conn.execute(
            "SELECT COUNT(DISTINCT feature) FROM fsm_state"
        ).fetchone()[0]
        events = conn.execute(
            "SELECT COUNT(*) FROM fsm_events WHERE event_type NOT IN ('BILLING_UPDATE')"
        ).fetchone()[0]
        invocations = conn.execute(
            "SELECT COUNT(*) FROM fsm_events WHERE event_type='AGENT_DONE'"
        ).fetchone()[0]
        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(CASE WHEN event_type='AGENT_DONE' "
            "    THEN CAST(json_extract(payload,'$.total_tokens') AS INT) ELSE 0 END),0), "
            "  COALESCE(SUM(CAST(json_extract(payload,'$.cost_usd') AS REAL)),0) "
            "FROM fsm_events WHERE event_type IN ('AGENT_DONE','BILLING_UPDATE')"
        ).fetchone()
        total_tokens = int(row[0])
        total_cost = float(row[1])

        if db_features_count == 0 and project_root:
            fs_features = _scan_filesystem_features(project_root)
            db_features_count = len(fs_features)
            total_cost += sum(f["cost_usd"] for f in fs_features)

        return jsonify(
            {
                "features": db_features_count,
                "events": events,
                "invocations": invocations,
                "total_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 4),
            }
        )
    except Exception as e:
        logger.exception("db_stats error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/features", methods=["GET"])
def db_features():
    """List all features — DB rows first, filesystem fallback for older features."""
    try:
        project_root = _project_root_param()
        conn = _get_db()

        pr_filter = project_root
        states: dict[tuple[str, str], dict] = {}
        if pr_filter:
            state_rows = conn.execute(
                "SELECT project_root, feature, state_json FROM fsm_state WHERE project_root=?",
                [pr_filter],
            ).fetchall()
        else:
            state_rows = conn.execute(
                "SELECT project_root, feature, state_json FROM fsm_state"
            ).fetchall()
        for r in state_rows:
            try:
                states[(r["project_root"], r["feature"])] = json.loads(r["state_json"])
            except (json.JSONDecodeError, TypeError):
                states[(r["project_root"], r["feature"])] = {}
        if pr_filter:
            event_count_rows = conn.execute(
                "SELECT project_root, feature, COUNT(*) as cnt FROM fsm_events"
                " WHERE project_root=? GROUP BY project_root, feature",
                [pr_filter],
            ).fetchall()
        else:
            event_count_rows = conn.execute(
                "SELECT project_root, feature, COUNT(*) as cnt FROM fsm_events GROUP BY project_root, feature"
            ).fetchall()
        event_counts = {
            (r["project_root"], r["feature"]): r["cnt"] for r in event_count_rows
        }
        if pr_filter:
            inv_rows = conn.execute(
                "SELECT project_root, feature, "
                "COUNT(CASE WHEN event_type='AGENT_DONE' THEN 1 END) as inv, "
                "COALESCE(SUM(CASE WHEN event_type='AGENT_DONE' "
                "  THEN CAST(json_extract(payload,'$.total_tokens') AS INT) ELSE 0 END),0) as total_tokens, "
                "COALESCE(SUM(CAST(json_extract(payload,'$.cost_usd') AS REAL)),0) as total_cost "
                "FROM fsm_events WHERE event_type IN ('AGENT_DONE','BILLING_UPDATE') AND project_root=? "
                "GROUP BY project_root, feature",
                [pr_filter],
            ).fetchall()
        else:
            inv_rows = conn.execute(
                "SELECT project_root, feature, "
                "COUNT(CASE WHEN event_type='AGENT_DONE' THEN 1 END) as inv, "
                "COALESCE(SUM(CASE WHEN event_type='AGENT_DONE' "
                "  THEN CAST(json_extract(payload,'$.total_tokens') AS INT) ELSE 0 END),0) as total_tokens, "
                "COALESCE(SUM(CAST(json_extract(payload,'$.cost_usd') AS REAL)),0) as total_cost "
                "FROM fsm_events WHERE event_type IN ('AGENT_DONE','BILLING_UPDATE') "
                "GROUP BY project_root, feature"
            ).fetchall()
        inv_stats = {(r["project_root"], r["feature"]): dict(r) for r in inv_rows}

        all_keys = set(states)
        results = []
        for pr, feat in sorted(all_keys, key=lambda x: x[1]):
            state_obj = states.get((pr, feat), {})
            inv = inv_stats.get((pr, feat), {})
            state_val = state_obj.get("current_state") or state_obj.get(
                "current", "UNKNOWN"
            )
            results.append(
                {
                    "project_root": pr,
                    "feature": feat,
                    "state": state_val.upper(),
                    "events": event_counts.get((pr, feat), 0),
                    "invocations": inv.get("inv", 0),
                    "total_tokens": int(inv.get("total_tokens", 0)),
                    "cost_usd": round(float(inv.get("total_cost", 0.0)), 4),
                    "updated_at": state_obj.get("updated_at", ""),
                    "convs_done": state_obj.get("convs_done", 0),
                    "convs_total": state_obj.get("convs_total", 0),
                    "source": "db",
                }
            )

        db_feature_names = {r["feature"] for r in results}
        if project_root:
            for fs_feat in _scan_filesystem_features(project_root):
                if fs_feat["feature"] not in db_feature_names:
                    results.append(fs_feat)

        return jsonify(sorted(results, key=lambda x: x["feature"]))
    except Exception as e:
        logger.exception("db_features error")
        return jsonify({"error": str(e)}), 500


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
        query = (
            "SELECT id, run_id, stage, agent_role, started_at, finished_at, "
            "tokens_in, tokens_out, cost_usd, session_id, summary "
            "FROM agent_invocations WHERE feature=?"
        )
        params: list = [feature]
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
            "start_time, end_time, attributes "
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
        query = (
            "SELECT id, run_id, status, started_at, finished_at, "
            "stage_count, total_tokens, cost_usd, adapter "
            "FROM run_history WHERE feature=?"
        )
        params: list = [feature]
        if pr:
            query += " AND project_root=?"
            params.append(pr)
        query += " ORDER BY id DESC"
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.exception("db_feature_runs error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/stats/trends", methods=["GET"])
def db_stats_trends():
    """Daily cost/token aggregates from otel_spans — last N days (default 30)."""
    try:
        conn = _get_db()
        pr = _project_root_param()
        days = min(int(request.args.get("days", 30)), 365)

        query = """
            SELECT
              date(start_time) AS day,
              COALESCE(ROUND(SUM(CAST(json_extract(attributes,'$.pathly.cost_usd') AS REAL)),6),0)       AS cost_usd,
              COALESCE(SUM(CAST(json_extract(attributes,'$.gen_ai.usage.input_tokens')  AS INTEGER)),0)  AS tokens_in,
              COALESCE(SUM(CAST(json_extract(attributes,'$.gen_ai.usage.output_tokens') AS INTEGER)),0)  AS tokens_out,
              COUNT(*) AS span_count
            FROM otel_spans
            WHERE start_time IS NOT NULL
              AND start_time >= date('now',?)
        """
        params: list = [f"-{days} days"]
        if pr:
            query += " AND project_root=?"
            params.append(pr)
        query += " GROUP BY date(start_time) ORDER BY day ASC"

        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.exception("db_stats_trends error")
        return jsonify({"error": str(e)}), 500
