"""DB explorer endpoints: stats, features list, trends, recent spawns.

Per-feature detail routes (/db/features/<feature>/{events,agents,otel,runs}) live in
db_api_feature_detail.py (SRP 400-line split).
"""

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


# Direct children of pathly/ that are containers, not features.
_RESERVED_PATHLY_SUBDIRS = {
    "plans",
    "features",
    "debugs",
    "explorations",
    "goals",
    ".archive",
    "pipeline-walkthrough",
}


def _scan_filesystem_features(project_root: str) -> list[dict]:
    """Scan for features not yet in the DB — the feature-centric roots Studio lists
    (``pathly/features|debugs|explorations/<name>/``), the legacy
    ``pathly/plans/<feature>/`` root, AND the older top-level ``pathly/<feature>/``
    root (reserved container dirs skipped).
    """
    results: list[dict] = []
    pathly_dir = Path(project_root) / "pathly"
    if not pathly_dir.is_dir():
        return results

    state_files = list((pathly_dir / "plans").glob("*/STATE.json"))
    # Current layout: the three roots Studio's HomeScreen scans. Without these a
    # never-run feature (STATE.json on disk, no DB row) would vanish from /db/features.
    for container in ("features", "debugs", "explorations"):
        state_files += list((pathly_dir / container).glob("*/STATE.json"))
    state_files += [
        sf
        for sf in pathly_dir.glob("*/STATE.json")
        if sf.parent.name not in _RESERVED_PATHLY_SUBDIRS
    ]

    seen: set[str] = set()
    for state_file in sorted(state_files):
        key = str(state_file.resolve())
        if key in seen:
            continue
        seen.add(key)
        feature_name = state_file.parent.name
        try:
            state = _parse_json_file(state_file)
        except Exception:
            continue

        current = state.get("current", "UNKNOWN").upper()
        updated_at = state.get("updated_at", "")

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
                # Never-run feature: no DB events, so no last_summary; flow comes
                # from the same parsed STATE.json when present (parity with DB rows).
                "last_summary": "",
                "flow": str(state.get("flow") or ""),
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
        # Cost + tokens read from agent_invocations — the SAME fact table the /db/rollup
        # scope-tier panels AND /db/features sum, so the header strip, the roll-up, and
        # the feature cards always agree. (The old fsm_events sum double-counted every
        # run that had both an AGENT_DONE and a superseding BILLING_UPDATE;
        # agent_invocations folds those into one row.) Scoped to project_root when given —
        # otherwise the header would show a global total next to per-project feature cards.
        if project_root:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens_in + tokens_out),0), "
                "       COALESCE(SUM(cost_usd),0) FROM agent_invocations WHERE project_root=?",
                (project_root,),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens_in + tokens_out),0), "
                "       COALESCE(SUM(cost_usd),0) FROM agent_invocations"
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
        # Read from agent_invocations — the SAME fact table /db/stats and /db/rollup sum
        # (one row per AGENT_DONE, the superseding BILLING_UPDATE folded in), so the
        # feature cards, the header strip, and the roll-up always agree. The old
        # fsm_events json_extract sum double-counted every run that had both an
        # AGENT_DONE and a BILLING_UPDATE. Keys (inv/total_tokens/total_cost) unchanged
        # so the loop below is untouched.
        if pr_filter:
            inv_rows = conn.execute(
                "SELECT project_root, feature, "
                "  COUNT(*) as inv, "
                "  COALESCE(SUM(tokens_in + tokens_out),0) as total_tokens, "
                "  COALESCE(SUM(cost_usd),0) as total_cost "
                "FROM agent_invocations WHERE project_root=? "
                "GROUP BY project_root, feature",
                [pr_filter],
            ).fetchall()
        else:
            inv_rows = conn.execute(
                "SELECT project_root, feature, "
                "  COUNT(*) as inv, "
                "  COALESCE(SUM(tokens_in + tokens_out),0) as total_tokens, "
                "  COALESCE(SUM(cost_usd),0) as total_cost "
                "FROM agent_invocations "
                "GROUP BY project_root, feature"
            ).fetchall()
        inv_stats = {(r["project_root"], r["feature"]): dict(r) for r in inv_rows}

        # state-one-authority: last_summary + flow let Studio read these off the DB row
        # instead of scanning EVENTS.jsonl / STATE.json mirrors directly.
        from pathly_orchestrator.db.queries.fsm_events import read_last_agent_done

        all_keys = set(states)
        results = []
        for pr, feat in sorted(all_keys, key=lambda x: x[1]):
            state_obj = states.get((pr, feat), {})
            inv = inv_stats.get((pr, feat), {})
            state_val = state_obj.get("current_state") or state_obj.get(
                "current", "UNKNOWN"
            )
            # Same (pr, feat) key the row is built from — so a goal-run feature
            # (keyed by its run slug) resolves its own AGENT_DONE, not the board scope's.
            last_done = read_last_agent_done(conn, pr, feat) or {}
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
                    "last_summary": str(last_done.get("summary") or ""),
                    "flow": str(state_obj.get("flow") or ""),
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


@bp.route("/db/stats/trends", methods=["GET"])
def db_stats_trends():
    """Daily cost/token aggregates from otel_spans — last N days (default 30)."""
    try:
        conn = _get_db()
        pr = _project_root_param()
        days = min(int(request.args.get("days", 30)), 365)

        # Span attributes are written FLAT by the telemetry writers (attributes.cost_usd,
        # attributes.tokens_in/out) — not under a '$.pathly'/'$.gen_ai' namespace. The
        # old paths matched nothing, so this endpoint always reported zero cost/tokens.
        query = """
            SELECT
              date(start_time) AS day,
              COALESCE(ROUND(SUM(CAST(json_extract(attributes,'$.cost_usd')   AS REAL)),6),0)  AS cost_usd,
              COALESCE(SUM(CAST(json_extract(attributes,'$.tokens_in')  AS INTEGER)),0)         AS tokens_in,
              COALESCE(SUM(CAST(json_extract(attributes,'$.tokens_out') AS INTEGER)),0)         AS tokens_out,
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


@bp.route("/db/recent", methods=["GET"])
def db_recent():
    """Recent spawns — the last N agent_invocations, newest first, for the monitor's RECENT/history
    list (DB-backed persistent history). Optional project_root scope; limit default 20, max 100.
    """
    try:
        conn = _get_db()
        pr = _project_root_param()
        limit = min(int(request.args.get("limit", 20)), 100)
        query = (
            "SELECT feature, agent_role, provider, run_id, "
            "  COALESCE(cost_usd,0) AS cost_usd, "
            "  (COALESCE(tokens_in,0) + COALESCE(tokens_out,0)) AS tokens, "
            "  finished_at, started_at, scope_tier, cost_source, category "
            "FROM agent_invocations"
        )
        params: list = []
        if pr:
            query += " WHERE project_root=?"
            params.append(pr)
        query += " ORDER BY COALESCE(finished_at, started_at) DESC, id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return jsonify([dict(r) for r in rows])
    except Exception as e:
        logger.exception("db_recent error")
        return jsonify({"error": str(e)}), 500
