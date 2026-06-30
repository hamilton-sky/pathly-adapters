"""Project an AGENT_DONE result into the telemetry tables (invocation + span).

The board / single / loop executors spawn agents WITHOUT registering a topic
`RunnerState`, so the FSM/team writer (`api_lifecycle._write_stage_telemetry`,
gated on a live RunnerState) never fires for them. This is the universal
projector that lights up those run types: one `agent_invocation` + one
`otel_span` per completed agent, tagged with its board `scope_tier` and threaded
into a goal trace.

Design (telemetry-three-tier): aggregate-on-read. Each call writes exactly ONE
append-only fact row addressed by (project_root, feature, scope_tier). Feature /
project / global totals are GROUP BYs over these rows — never stored counters,
so there is nothing to double-count or keep in sync.

Best-effort everywhere: telemetry must never break an executor.
"""

from __future__ import annotations

import json as _json
import logging
import uuid
from datetime import datetime, timedelta, timezone

_log = logging.getLogger("pathly.telemetry")

_VALID_TIERS = ("feature", "project", "global")


def scope_tier_for(board: str | None) -> str:
    """Map a board name to its scope tier tag.

    Under the Board→Goals model the board name IS the tier
    ('feature'|'project'|'global'). Anything else defaults to 'feature'.
    """
    b = (board or "").strip().lower()
    return b if b in _VALID_TIERS else "feature"


def new_trace_id() -> str:
    """32-hex OTel-style trace id."""
    return uuid.uuid4().hex


def new_span_id() -> str:
    """16-hex OTel-style span id."""
    return uuid.uuid4().hex[:16]


def write_goal_root_span(
    *,
    project_root: str,
    feature: str,
    goal_id: str,
    trace_id: str,
    span_id: str,
    scope_tier: str = "feature",
    executor: str = "",
) -> None:
    """Write the root span for a goal run (goal=trace). Task spans hang under it.

    Best-effort — a missing root span only means the trace tree has no labelled
    root, not that task spans are lost.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.otel_spans import write_otel_span

        now = datetime.now(timezone.utc).isoformat()
        write_otel_span(
            get_db(),
            project_root,
            feature,
            name=f"goal:{goal_id}",
            trace_id=trace_id or None,
            span_id=span_id or new_span_id(),
            parent_span_id=None,
            start_time=now,
            end_time=now,
            scope_tier=scope_tier,
            attributes=_json.dumps(
                {"goal_id": goal_id, "executor": executor, "scope_tier": scope_tier}
            ),
        )
    except Exception:
        _log.debug("write_goal_root_span skipped", exc_info=True)


def project_agent_done(
    *,
    project_root: str,
    feature: str,
    agent_done: dict | None,
    run_id: str,
    stage: str = "",
    agent_role: str = "",
    scope_tier: str = "feature",
    adapter: str = "",
    tool_uses: int = 0,
    trace_id: str = "",
    span_id: str = "",
    parent_span_id: str = "",
    wall_seconds: float = 0.0,
) -> None:
    """Write ONE agent_invocation + ONE otel_span from an AGENT_DONE payload.

    `agent_done` is the dict read from the central DB's last AGENT_DONE (or the
    parsed PTY result) — cost_usd / tokens_in / tokens_out / summary / session_id.
    Never raises.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.invocations import write_agent_invocation
        from pathly_orchestrator.db.queries.otel_spans import write_otel_span

        ad = agent_done or {}
        tier = scope_tier_for(scope_tier)
        cost = float(ad.get("cost_usd") or 0.0)
        tin = int(ad.get("tokens_in") or 0)
        tout = int(ad.get("tokens_out") or 0)
        summary = ad.get("summary") or ad.get("result") or ""
        session_id = ad.get("session_id")
        role = agent_role or ad.get("agent") or stage or "agent"
        sid = span_id or new_span_id()
        end_dt = datetime.now(timezone.utc)
        start_dt = end_dt - timedelta(seconds=float(wall_seconds or 0))

        conn = get_db()
        write_otel_span(
            conn,
            project_root,
            feature,
            name=stage or role,
            trace_id=trace_id or None,
            span_id=sid,
            parent_span_id=parent_span_id or None,
            start_time=start_dt.isoformat(),
            end_time=end_dt.isoformat(),
            scope_tier=tier,
            attributes=_json.dumps(
                {
                    "agent": role,
                    "cost_usd": cost,
                    "tokens_in": tin,
                    "tokens_out": tout,
                    "scope_tier": tier,
                    "run_id": run_id,
                    "adapter": adapter,
                    "tool_uses": tool_uses,
                }
            ),
        )
        write_agent_invocation(
            conn,
            project_root,
            feature,
            {
                "run_id": run_id,
                "stage": stage,
                "agent_role": role,
                "started_at": start_dt.isoformat(),
                "finished_at": end_dt.isoformat(),
                "tokens_in": tin,
                "tokens_out": tout,
                "cost_usd": cost,
                "session_id": session_id,
                "summary": (summary or "")[:2000],
                "scope_tier": tier,
            },
        )
    except Exception:
        _log.debug("project_agent_done skipped", exc_info=True)
