"""Stop hook: write BILLING_UPDATE to DB with real session cost.

Claude Code fires this when the model stops. The payload on stdin contains
session usage data (tokens, cost). We find the most recently active feature
in the DB and append a BILLING_UPDATE event so Studio can display real costs.

Also supports legacy EVENTS.jsonl patching for repos that still write files
(PATHLY_DB_ONLY=0).

Exits 0 always — telemetry failure must never block the user.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def _find_active_feature_dir_db(project_root: str) -> Path | None:
    """Find the feature dir with the most recent event in the SQLite DB."""
    try:
        from pathly_orchestrator.db import get_db as _get_db
        conn = _get_db()
        row = conn.execute(
            "SELECT feature FROM fsm_events WHERE project_root=? ORDER BY seq DESC LIMIT 1",
            (_norm(project_root),),
        ).fetchone()
        if row:
            feature = row["feature"] if hasattr(row, "keys") else row[0]
            return Path(project_root) / "pathly" / "plans" / feature
    except Exception:
        pass
    return None


def _find_active_events_file(project_root: str) -> Path | None:
    """Return the most recently modified EVENTS.jsonl under pathly/plans/ (legacy)."""
    plans = Path(project_root) / "pathly" / "plans"
    if not plans.exists():
        return None
    candidates = [p for p in plans.rglob("EVENTS.jsonl") if ".archive" not in p.parts]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def _patch_last_agent_done_file(
    events_file: Path,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
) -> bool:
    """Patch the last AGENT_DONE line in EVENTS.jsonl (legacy path). Returns True if patched."""
    try:
        lines = events_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return False

    for i in range(len(lines) - 1, -1, -1):
        line = lines[i].strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "AGENT_DONE":
            if event.get("tokens_in", 0) == 0 and event.get("cost_usd", 0.0) == 0.0:
                event["tokens_in"] = tokens_in
                event["tokens_out"] = tokens_out
                event["cost_usd"] = round(cost_usd, 6)
                lines[i] = json.dumps(event)
                tmp = events_file.with_suffix(".tmp")
                try:
                    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
                    tmp.replace(events_file)
                    return True
                except OSError:
                    tmp.unlink(missing_ok=True)
            return False
    return False


def _write_billing_update_db(
    feature_dir: Path,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
) -> bool:
    """Append a BILLING_UPDATE event to the DB for the last AGENT_DONE.

    Returns True if successfully written.
    """
    try:
        from pathly_orchestrator.runner.events import _patch_last_agent_done
        _patch_last_agent_done(
            storage_path=feature_dir,
            cost_usd=cost_usd,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            wall_seconds=0,
        )
        return True
    except Exception:
        pass

    # Fallback: write raw BILLING_UPDATE directly to DB without going through runner
    try:
        from pathly_orchestrator.db import get_db as _get_db, append_event as _db_ae
        conn = _get_db()
        project_root = _norm(str(feature_dir.parent.parent.parent))
        feature = feature_dir.name
        # Find last AGENT_DONE for agent/conv labelling
        last = conn.execute(
            "SELECT payload FROM fsm_events WHERE project_root=? AND feature=? "
            "AND event_type='AGENT_DONE' ORDER BY seq DESC LIMIT 1",
            (project_root, feature),
        ).fetchone()
        payload_row = last[0] if last else None
        last_event = json.loads(payload_row) if payload_row else {}
        billing: dict = {
            "type": "BILLING_UPDATE",
            "agent": last_event.get("agent"),
            "conversation": last_event.get("conversation"),
            "cost_usd": cost_usd,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "wall_seconds": 0,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "schema_version": 1,
        }
        _db_ae(conn, project_root, feature, billing)
        conn.commit()
        return True
    except Exception:
        pass

    return False


def main() -> None:
    # Read stop hook payload
    try:
        payload = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, OSError):
        sys.exit(0)

    # Extract usage — try multiple field layouts (Claude Code varies by version)
    usage = payload.get("usage") or {}
    tokens_in = int(
        usage.get("input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
    )
    tokens_out = int(usage.get("output_tokens", 0))
    cost_usd = float(
        payload.get("total_cost_usd")
        or payload.get("cost_usd")
        or payload.get("totalCostUsd")
        or 0.0
    )

    # Nothing useful — exit cleanly
    if tokens_in == 0 and cost_usd == 0.0:
        sys.exit(0)

    project_root = _norm(os.environ.get("PATHLY_PROJECT_ROOT", ""))
    if not project_root:
        sys.exit(0)

    # Try legacy EVENTS.jsonl path first (PATHLY_DB_ONLY=0 repos)
    events_file = _find_active_events_file(project_root)
    if events_file:
        _patch_last_agent_done_file(events_file, tokens_in, tokens_out, cost_usd)
        # Also write BILLING_UPDATE to DB so Studio sees it
        feature_dir = events_file.parent
        _write_billing_update_db(feature_dir, tokens_in, tokens_out, cost_usd)
        sys.exit(0)

    # DB-only mode: find active feature from DB and write BILLING_UPDATE
    feature_dir = _find_active_feature_dir_db(project_root)
    if feature_dir:
        _write_billing_update_db(feature_dir, tokens_in, tokens_out, cost_usd)

    sys.exit(0)


if __name__ == "__main__":
    main()
