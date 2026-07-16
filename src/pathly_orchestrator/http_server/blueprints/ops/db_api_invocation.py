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
      cost_usd      number         — fallback cost if no stdout_tail / server parse finds none
      tokens_in     int            — fallback; default 0
      tokens_out    int            — fallback; default 0
      stdout_tail   str            — raw CLI stdout; parsed server-side by parse_result (the ONE
                                     robust parser) and PREFERRED over the client cost/tokens above
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

        # Unified telemetry parse (spawn-parse-unification): if the client sends the raw CLI
        # stdout, parse cost/tokens with the ONE server-side parser — runner/output.py::parse_result,
        # the same robust parser (incl. truncation recovery) that runner spawns use — instead of
        # trusting a second, drift-prone client-side parser. This is why claude editor one-shots
        # recorded $0: the Studio parser bailed on a truncated envelope. The client-parsed cost/
        # tokens above stay as a FALLBACK (older clients / when the server parse finds nothing), so
        # a good client parse never regresses to $0.
        stdout_tail = body.get("stdout_tail") or ""
        if stdout_tail and adapter:
            try:
                from pathly_orchestrator.runner import parse_result

                parsed = parse_result(adapter, stdout_tail)
                p_cost = float(parsed.get("cost_usd") or 0)
                p_in = int(parsed.get("tokens_in") or 0)
                p_out = int(parsed.get("tokens_out") or 0)
                if p_cost > 0:
                    cost_usd = p_cost
                if (p_in + p_out) > 0:
                    tokens_in, tokens_out = p_in, p_out
                if not tool_uses and parsed.get("tool_uses"):
                    tool_uses = int(parsed.get("tool_uses") or 0)
                if not summary and parsed.get("result"):
                    summary = str(parsed.get("result"))[:2000]
            except Exception:
                logger.debug("db_invocation: server-side parse skipped", exc_info=True)

        from pathly_orchestrator.runner.telemetry import (
            new_trace_id,
            project_agent_done,
        )

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
