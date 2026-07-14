"""Stop hook: write BILLING_UPDATE to DB with real session cost.

Claude Code fires this when the model stops. The payload on stdin contains
session usage data (tokens, cost).

DEMOTED to a FALLBACK (adapter-agnostic billing refactor): the spawn gate now bills
every runner spawn authoritatively (run-keyed, any adapter) via /runner/terminal/result,
so those carry ``PATHLY_GATE_BILLED`` and this hook SKIPS them — it would otherwise
double-bill / mis-attribute, since it can only guess the target via "the most recently
active feature" (racy under concurrent/goal runs). This hook now bills ONLY INTERACTIVE
claude sessions (no runner tab, no result callback) — the one case with no other source.

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
            # Resolve the feature's flat home via the single resolver (pathly/features/<name>/),
            # not the legacy hardcoded pathly/plans/<name> — the feature lives under features/.
            from pathly_orchestrator.fsm_ops import _resolve_storage_path

            return _resolve_storage_path(None, project_root, feature)
    except Exception:
        pass
    return None


def _write_billing_update_db(
    feature_dir: Path,
    tokens_in: int,
    tokens_out: int,
    cost_usd: float,
    cost_source: str,
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
            "cost_source": cost_source,
        }
        _db_ae(conn, project_root, feature, billing)
        conn.commit()
        return True
    except Exception:
        pass

    return False


def main() -> None:
    # Runner spawns are billed authoritatively by the spawn gate (adapter-agnostic, run-keyed)
    # via /runner/terminal/result and carry this marker — SKIP them so this claude-only hook
    # doesn't double-bill or mis-attribute. Interactive claude sessions carry no marker and fall
    # through to be billed here (their only cost source).
    if os.environ.get("PATHLY_GATE_BILLED"):
        sys.exit(0)

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

    cost_source = "provider_reported" if cost_usd > 0 else "unpriced"

    # Find active feature from DB and write BILLING_UPDATE
    feature_dir = _find_active_feature_dir_db(project_root)
    if feature_dir:
        _write_billing_update_db(
            feature_dir, tokens_in, tokens_out, cost_usd, cost_source
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
