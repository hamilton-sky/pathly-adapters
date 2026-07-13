"""DB rollup endpoint: feature -> project -> global telemetry, aggregate-on-read.

The three tiers are GROUP BYs over the single `agent_invocations` fact table — never
stored counters. Project = sum over every feature/topic under a project_root; global =
sum over everything. Because each agent writes exactly ONE fact row, no level can
double-count: global is the same rows project reads, just a wider WHERE.
"""

from __future__ import annotations

from flask import jsonify, request

from ._db_api_bp import _get_db, _project_root_param, bp, logger

_TIERS = ("feature", "project", "global")


def _by_tier(conn, where_sql: str, params: list) -> dict:
    """Return {tier: {invocations, cost_usd, tokens_in, tokens_out}} for a WHERE clause."""
    rows = conn.execute(
        "SELECT COALESCE(scope_tier,'feature') AS tier, "  # nosec B608 - where_sql is internally built; values are bound
        "  COUNT(*) AS invocations, "
        "  COALESCE(SUM(cost_usd),0) AS cost_usd, "
        "  COALESCE(SUM(tokens_in),0) AS tokens_in, "
        "  COALESCE(SUM(tokens_out),0) AS tokens_out "
        f"FROM agent_invocations {where_sql} GROUP BY COALESCE(scope_tier,'feature')",
        params,
    ).fetchall()
    out = {
        t: {"invocations": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0}
        for t in _TIERS
    }
    for r in rows:
        tier = r["tier"] if r["tier"] in _TIERS else "feature"
        out[tier] = {
            "invocations": int(r["invocations"]),
            "cost_usd": round(float(r["cost_usd"]), 6),
            "tokens_in": int(r["tokens_in"]),
            "tokens_out": int(r["tokens_out"]),
        }
    return out


def _totals(by_tier: dict) -> dict:
    """Sum the per-tier slices into one totals block."""
    return {
        "invocations": sum(v["invocations"] for v in by_tier.values()),
        "cost_usd": round(sum(v["cost_usd"] for v in by_tier.values()), 6),
        "tokens_in": sum(v["tokens_in"] for v in by_tier.values()),
        "tokens_out": sum(v["tokens_out"] for v in by_tier.values()),
    }


@bp.route("/db/rollup", methods=["GET"])
def db_rollup():
    """Feature -> project -> global telemetry roll-up, broken down by scope_tier.

    Query params:
      project_root  — when set, the `project` block sums only this root; the `global`
                      block always spans every project.
      feature       — optional; when set, a `feature` block sums just that feature.

    Shape:
      { project: {root, by_tier, totals},
        global:  {by_tier, totals, by_project[]},
        feature?: {feature, by_tier, totals} }
    """
    try:
        conn = _get_db()
        pr = _project_root_param()
        feature = (request.args.get("feature") or "").strip()

        # global — everything, the widest WHERE (none)
        g_by_tier = _by_tier(conn, "", [])

        # global breakdown by project_root (so the UI can list every project under global)
        proj_rows = conn.execute(
            "SELECT project_root, COUNT(*) AS invocations, "
            "  COALESCE(SUM(cost_usd),0) AS cost_usd, "
            "  COALESCE(SUM(tokens_in),0) AS tokens_in, "
            "  COALESCE(SUM(tokens_out),0) AS tokens_out "
            "FROM agent_invocations GROUP BY project_root ORDER BY cost_usd DESC"
        ).fetchall()
        by_project = [
            {
                "project_root": r["project_root"],
                "invocations": int(r["invocations"]),
                "cost_usd": round(float(r["cost_usd"]), 6),
                "tokens_in": int(r["tokens_in"]),
                "tokens_out": int(r["tokens_out"]),
            }
            for r in proj_rows
        ]
        global_block = {
            "by_tier": g_by_tier,
            "totals": _totals(g_by_tier),
            "by_project": by_project,
        }

        # project — sums every feature/topic under this project_root
        p_by_tier = (
            _by_tier(conn, "WHERE project_root=?", [pr])
            if pr
            else _by_tier(conn, "WHERE 1=0", [])
        )
        project_block = {"root": pr, "by_tier": p_by_tier, "totals": _totals(p_by_tier)}

        result = {"project": project_block, "global": global_block}

        if feature:
            params: list = [feature]
            where = "WHERE feature=?"
            if pr:
                where += " AND project_root=?"
                params.append(pr)
            f_by_tier = _by_tier(conn, where, params)
            result["feature"] = {
                "feature": feature,
                "by_tier": f_by_tier,
                "totals": _totals(f_by_tier),
            }

        return jsonify(result)
    except Exception as e:
        logger.exception("db_rollup error")
        return jsonify({"error": str(e)}), 500


@bp.route("/db/runs/<run_id>/cost", methods=["GET"])
def db_run_cost(run_id: str):
    """Per-flow (run_id) cost/token rollup.

    Every agent_invocations row is already billing-reconciled (the projector folds a
    superseding BILLING_UPDATE into its anchor row — see invocation_projection.py), so
    a plain SUM over run_id is correct with no double-count. Zeros (not 404) for an
    unknown run_id — there is no "run not found" error state, just no facts yet.
    """
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT COUNT(*) AS invocations, "
            "  COALESCE(SUM(cost_usd),0) AS cost_usd, "
            "  COALESCE(SUM(tokens_in),0) AS tokens_in, "
            "  COALESCE(SUM(tokens_out),0) AS tokens_out "
            "FROM agent_invocations WHERE run_id=?",
            (run_id,),
        ).fetchone()
        tokens_in = int(row["tokens_in"])
        tokens_out = int(row["tokens_out"])
        return jsonify(
            {
                "run_id": run_id,
                "invocations": int(row["invocations"]),
                "cost_usd": round(float(row["cost_usd"]), 6),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "tokens_total": tokens_in + tokens_out,
            }
        )
    except Exception as e:
        logger.exception("db_run_cost error")
        return jsonify({"error": str(e)}), 500
