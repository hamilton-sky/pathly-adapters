"""Best-effort artifact reconciliation: read ARTIFACTS.jsonl, attach to the board."""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger("pathly.supervisor")


def reconcile_artifacts(
    storage_path: Path,
    scope: str,
    *,
    goal_id: str | None = None,
    board: str = "feature",
    broadcast_fn=None,
) -> int:
    """Read <storage_path>/ARTIFACTS.jsonl and ensure each artifact is attached.

    Best-effort and non-fatal: never raises. Returns the count attached.
    The ledger (written by the artifact-register fragment) is the source; this
    closes the gap when the agent's advisory board POST was skipped (server down).
    """
    ledger = Path(storage_path) / "ARTIFACTS.jsonl"
    if not ledger.exists():
        return 0
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_artifacts import ensure_attached
    except Exception as exc:  # pragma: no cover
        logger.warning("reconcile_artifacts: import failed: %s", exc)
        return 0
    n = 0
    try:
        conn = get_db()
        for line in ledger.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            path = rec.get("path")
            if not path:
                continue
            try:
                ensure_attached(
                    conn,
                    scope,
                    path,
                    board=board,
                    goal_id=goal_id,
                    role=rec.get("role"),
                    title=rec.get("title"),
                    summary=rec.get("summary"),
                    type=rec.get("type", "md"),
                    broadcast_fn=broadcast_fn,
                )
                n += 1
            except Exception as exc:
                logger.warning(
                    "reconcile_artifacts: attach failed for %s: %s", path, exc
                )
    except Exception as exc:
        logger.warning("reconcile_artifacts: failed: %s", exc)
    return n
