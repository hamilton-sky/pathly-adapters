"""DB invocation ingestion endpoint: POST /db/invocation.

Accepts client-side one-shot telemetry from Studio (renderer-driven CLI actions
such as editor AI actions and HQ chat summaries) that never pass through the
Python supervisor.  Calls the universal projector `project_agent_done` so these
runs appear in /db/rollup alongside supervisor-driven runs.

Best-effort: the handler never returns 5xx — on any exception it logs and
returns {"ok": False} with HTTP 200.  Only a missing/empty project_root returns
400.
"""

from __future__ import annotations

import logging

from flask import jsonify, request

from ._db_api_bp import bp

logger = logging.getLogger("pathly.http")


@bp.route("/db/invocation", methods=["POST"])
def db_invocation():
    """Ingest a single renderer-side CLI one-shot into the telemetry tables.

    Request JSON (all optional except project_root):
      project_root  str            — required; 400 if missing/empty
      feature       str            — default "(project)"
      scope_tier    str            — 'feature'|'project'|'global'; default "project"
      run_id        str            — default ""
      label         str            — action name (maps to stage); default ""
      agent_role    str            — default ""
      adapter       str            — default ""
      cost_usd      number         — default 0
      tokens_in     int            — default 0
      tokens_out    int            — default 0
      session_id    str|null       — default null
      summary       str            — default ""
      wall_seconds  number         — default 0
    """
    try:
        body = request.get_json(silent=True) or {}

        project_root = (body.get("project_root") or "").strip()
        if not project_root:
            return jsonify({"error": "project_root is required"}), 400

        feature = (body.get("feature") or "(project)").strip() or "(project)"
        scope_tier = (body.get("scope_tier") or "project").strip() or "project"
        run_id = body.get("run_id") or ""
        label = body.get("label") or ""
        agent_role = body.get("agent_role") or ""
        adapter = body.get("adapter") or ""
        cost_usd = float(body.get("cost_usd") or 0)
        tokens_in = int(body.get("tokens_in") or 0)
        tokens_out = int(body.get("tokens_out") or 0)
        tool_uses = int(body.get("tool_uses") or 0)
        session_id = body.get("session_id") or None
        summary = body.get("summary") or ""
        wall_seconds = float(body.get("wall_seconds") or 0)

        from pathly_orchestrator.runner.telemetry import new_trace_id, project_agent_done

        trace_id = new_trace_id()
        project_agent_done(
            project_root=project_root,
            feature=feature,
            agent_done={
                "cost_usd": cost_usd,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "summary": summary,
                "session_id": session_id,
                "agent": agent_role,
            },
            run_id=run_id,
            stage=label,
            agent_role=agent_role,
            scope_tier=scope_tier,
            adapter=adapter,
            tool_uses=tool_uses,
            trace_id=trace_id,
            wall_seconds=wall_seconds,
        )
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("db_invocation error")
        return jsonify({"ok": False, "error": str(exc)}), 200
