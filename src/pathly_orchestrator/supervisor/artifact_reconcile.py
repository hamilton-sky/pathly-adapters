"""Best-effort artifact reconciliation: surface stage outputs + feedback files on the board."""

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
    """Ensure a stage's/goal's outputs + feedback files are attached to the board.

    Two sources, both best-effort and non-fatal (never raises); returns the count attached:
      1. ``<storage_path>/ARTIFACTS.jsonl`` — the ledger written by the artifact-register
         fragment (a stage's declared ``<out_path>`` outputs); closes the gap when the agent's
         advisory board POST was skipped (server down).
      2. ``<storage_path>/feedback/*.md`` — agent/system feedback files (HUMAN_QUESTIONS.md,
         REVIEW_FAILURES.md, TEST_FAILURES.md, …). These are never a stage ``<out_path>`` so they
         never reach the ledger, yet they are exactly what a human needs to see — surface them as
         board artifacts. ``ensure_attached`` is idempotent on ``(scope, path)`` so re-scans
         (this runs after every stage/goal) never duplicate.
    """
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms_artifacts import ensure_attached
    except Exception as exc:  # pragma: no cover
        logger.warning("reconcile_artifacts: import failed: %s", exc)
        return 0
    try:
        conn = get_db()
    except Exception as exc:  # pragma: no cover
        logger.warning("reconcile_artifacts: get_db failed: %s", exc)
        return 0

    n = 0

    # 1) Declared artifacts from the ledger.
    ledger = Path(storage_path) / "ARTIFACTS.jsonl"
    if ledger.exists():
        try:
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
            logger.warning("reconcile_artifacts: ledger read failed: %s", exc)

    # 2) Feedback files — agent/system output the human must see, but never in the ledger.
    try:
        fb_dir = Path(storage_path) / "feedback"
        if fb_dir.is_dir():
            for fb in sorted(fb_dir.glob("*.md")):
                try:
                    ensure_attached(
                        conn,
                        scope,
                        str(fb),
                        board=board,
                        goal_id=goal_id,
                        role="system",
                        title=fb.stem.replace("_", " ").title(),
                        type="md",
                        broadcast_fn=broadcast_fn,
                    )
                    n += 1
                except Exception as exc:
                    logger.warning(
                        "reconcile_artifacts: feedback attach failed for %s: %s", fb, exc
                    )
    except Exception as exc:
        logger.warning("reconcile_artifacts: feedback scan failed: %s", exc)

    return n
