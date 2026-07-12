"""Board disk-mirror hydration (P2) — import BOARD.json mirrors back into the DB.

Sibling to ``board_mirror.py`` (which stays export-only / DB -> disk) to keep that
file under the project's 400-line cap; re-exported from it at the bottom for the
conventional import path. The DB stays authoritative: hydration only fills a board
that has ZERO rows in the DB — an existing board is never touched, mirroring the
``STATE.json`` fallback pattern (``next_action``/``complete_stage`` read the DB
first, the file only when the DB has no row).
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact_row
from pathly_orchestrator.db.queries.comms_messages import (
    get_all_messages,
    insert_message_row,
)

logger = logging.getLogger("pathly.board_mirror")


def hydrate_board(conn: sqlite3.Connection, board: str, scope: str, path: Path) -> bool:
    """Import *path* (a BOARD.json snapshot) into the DB for (board, scope).

    DB stays authoritative: if ``get_all_messages`` already returns rows for this
    (board, scope), this is a no-op (returns False) — an existing board is NEVER
    overwritten by a stale or divergent mirror. Otherwise every message/artifact row
    in the snapshot is inserted (full-fidelity, idempotent) and each inserted message
    is best-effort re-embedded — the rows landing in the DB are hydration's whole
    value, so a missing/broken embedder must never block or fail it. Never raises.
    """
    try:
        if get_all_messages(conn, board, scope):
            return False
        if not path.exists():
            return False
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("hydrate_board failed to read %s", path, exc_info=True)
        return False

    messages = snapshot.get("messages") or []
    artifacts = snapshot.get("artifacts") or []

    for msg in messages:
        insert_message_row(conn, msg)
    for art in artifacts:
        insert_artifact_row(conn, art)

    _embed_fn = None
    try:
        from pathly_orchestrator.runner.embeddings import (
            embed_artifact_async as _embed_fn,
        )
    except Exception:
        pass  # embedder unavailable — hydration still succeeded, skip re-embed silently

    if _embed_fn is not None:
        summary_by_msg = {
            a["message_id"]: a.get("summary") or ""
            for a in artifacts
            if a.get("message_id")
        }
        for msg in messages:
            mid = msg.get("id")
            if not mid:
                continue
            try:
                text = msg.get("text") or ""
                summary = summary_by_msg.get(mid, "")
                parent_text = f"{text}\n\n{summary}".strip() if summary else text
                _embed_fn(mid, parent_text, summary)
            except Exception:
                logger.debug("hydrate_board: re-embed failed id=%s", mid, exc_info=True)

    return True


def hydrate_project(conn: sqlite3.Connection, project_root: str) -> dict:
    """Hydrate every discoverable board mirror for *project_root*: the project board,
    each ``pathly/features/<feature>/BOARD.json``, and the global board. Only files
    that exist on disk are attempted. Returns ``{"hydrated": [<scope>...], "skipped":
    [<scope>...]}`` — best-effort, never raises.
    """
    hydrated: list[str] = []
    skipped: list[str] = []
    try:
        from pathly_orchestrator.board_mirror import (
            _norm_project_root,
            board_mirror_path,
        )

        root = _norm_project_root(project_root)
        candidates: list[tuple[str, str]] = []
        if root:
            candidates.append(("project", root))
            features_dir = Path(root) / "pathly" / "features"
            if features_dir.is_dir():
                for feat_dir in sorted(features_dir.iterdir()):
                    if feat_dir.is_dir():
                        candidates.append(("feature", feat_dir.name))
        candidates.append(("global", "global"))

        for board, scope in candidates:
            path = board_mirror_path(board, scope, root)
            if path is None or not path.exists():
                continue
            if hydrate_board(conn, board, scope, path):
                hydrated.append(scope)
            else:
                skipped.append(scope)
    except Exception:
        logger.debug(
            "hydrate_project failed for project_root=%s", project_root, exc_info=True
        )

    return {"hydrated": hydrated, "skipped": skipped}
