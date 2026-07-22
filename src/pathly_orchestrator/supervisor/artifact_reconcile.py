"""Best-effort artifact reconciliation: surface stage outputs + feedback files on the board."""

from __future__ import annotations

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
    out_path: str | None = None,
) -> int:
    """Ensure a stage's/goal's outputs + feedback files are attached to the board.

    Two sources, both best-effort and non-fatal (never raises); returns the count attached:
      1. ``out_path`` (optional) — the calling stage's declared primary output, resolved from
         the FSM's own composition manifest (``fsm_compose.resolve_stage_out_path``) and attached
         directly. Closes the server-down gap when the agent's advisory board POST was skipped —
         WITHOUT a disk ledger (state-one-authority: the ``ARTIFACTS.jsonl`` ledger is dropped, its
         artifact metadata already lives in ``BOARD.json``). Skipped when None or the file is absent.
      2. ``<storage_path>/feedback/*.md`` — agent/system feedback files (HUMAN_QUESTIONS.md,
         REVIEW_FAILURES.md, TEST_FAILURES.md, …). These are never a stage ``<out_path>`` so they
         never reach source 1, yet they are exactly what a human needs to see — surface them as
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

    # 1) The stage's declared output — attached from the FSM's own record (no disk ledger).
    if out_path:
        try:
            p = Path(out_path)
            if p.exists():
                ensure_attached(
                    conn,
                    scope,
                    out_path,
                    board=board,
                    goal_id=goal_id,
                    title=p.stem.replace("_", " ").title(),
                    type="md",
                    broadcast_fn=broadcast_fn,
                )
                n += 1
        except Exception as exc:
            logger.warning(
                "reconcile_artifacts: out_path attach failed for %s: %s", out_path, exc
            )

    # 2) Feedback files — agent/system output the human must see, but never a stage <out_path>.
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
                        "reconcile_artifacts: feedback attach failed for %s: %s",
                        fb,
                        exc,
                    )
    except Exception as exc:
        logger.warning("reconcile_artifacts: feedback scan failed: %s", exc)

    return n
