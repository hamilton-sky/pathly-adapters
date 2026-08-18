"""Supervisor-authored phase summaries.

Split from ``terminal`` because it writes a board artifact, not a process: it runs after a
stage settles and touches none of the spawn machinery.
"""

from __future__ import annotations

from pathlib import Path

from .state import logger


def _write_supervisor_phase_summary(
    *,
    project_root: str,
    topic: str,
    stage: str,
    agent: str,
    text: str,
    broadcast_fn=None,
) -> None:
    """Write a PHASE_SUMMARY event to the feature's SQLite DB and broadcast to Studio via SSE."""
    import time as _time

    if not project_root or not topic:
        return
    try:
        from pathly_orchestrator import db as _db
        from pathly_orchestrator.fsm_ops import _load_flow, _resolve_storage_path

        try:
            flow_config = _load_flow("team")
            feature_dir = _resolve_storage_path(flow_config, project_root, topic)
        except Exception:
            feature_dir = Path(project_root) / "pathly" / "features" / topic
        if not feature_dir.exists():
            return
        conn = _db.get_db()
        phase = stage.lower().replace("-", "_") if stage else ""
        event: dict = {
            "schema_version": 1,
            "type": "PHASE_SUMMARY",
            "feature": topic,
            "agent": agent,
            "text": text,
            "ts": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        }
        if phase:
            event["phase"] = phase
        _db.append_event(conn, project_root, topic, event)
        # Broadcast to Studio so live log cards update in headless mode
        if broadcast_fn:
            try:
                broadcast_fn(topic, event)
            except Exception:
                pass
    except Exception:
        logger.debug("_write_supervisor_phase_summary failed", exc_info=True)
