"""
BoardMirror — export the comms board (messages + artifact metadata) to disk.

The central DB (``~/.pathly/pathly.db``, tables ``comms_messages`` + ``comms_artifacts``)
stays the runtime system of record; this module writes a synchronized, git-trackable
JSON snapshot of each board next to its owning feature/project — the same pattern
``eventlog._write_state_db`` uses for ``STATE.json``: temp file + atomic replace.

P0 scope only: path resolver + atomic exporter + idempotent startup backfill. Pure
DB -> disk export, never the other direction — no live write hook (P1) and no
hydration/import back into the DB (P2).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from pathlib import Path

from pathly_orchestrator.db.queries.comms_artifacts import list_artifacts_for_messages
from pathly_orchestrator.db.queries.comms_messages import get_all_messages

logger = logging.getLogger("pathly.board_mirror")


def _norm_project_root(project_root: str | None) -> str | None:
    """Canonicalize a project root (forward slashes, no trailing slash) so it matches
    the scope string other write paths store for board='project' rows. Mirrors
    ``db/queries/skill_composition.py::_norm_root`` / ``comms/project.py::_project_scope``.
    """
    if not project_root:
        return None
    norm = str(project_root).replace("\\", "/").rstrip("/")
    return norm or None


def board_mirror_path(board: str, scope: str, project_root: str | None) -> Path | None:
    """Resolve the on-disk BOARD.json path for a (board, scope). None if unresolvable.

    - "global"  -> ~/.pathly/global/BOARD.json (project_root ignored)
    - "project" -> <project_root>/pathly/project/BOARD.json (None with no project_root)
    - "feature" -> <project_root>/pathly/features/<scope>/BOARD.json (None with no project_root)
    - anything else -> None
    """
    if board == "global":
        return Path.home() / ".pathly" / "global" / "BOARD.json"
    if board not in ("project", "feature"):
        return None
    root = _norm_project_root(project_root)
    if not root:
        return None
    if board == "project":
        return Path(root) / "pathly" / "project" / "BOARD.json"
    return Path(root) / "pathly" / "features" / scope / "BOARD.json"


def serialize_board(conn: sqlite3.Connection, board: str, scope: str) -> dict:
    """Snapshot dict for (board, scope): every live message (non-deleted, stable-sorted
    by ts,id) plus the comms_artifacts metadata rows linked to them. Embeddings are
    never included — they are a derived search index, rebuilt on hydration (P2).
    """
    messages = get_all_messages(conn, board, scope)
    message_ids = [m["id"] for m in messages]
    artifacts = list_artifacts_for_messages(conn, message_ids)
    return {
        "board": board,
        "scope": scope,
        "version": 1,
        "messages": messages,
        "artifacts": artifacts,
    }


def write_board_mirror(
    conn: sqlite3.Connection, board: str, scope: str, project_root: str | None
) -> bool:
    """Atomically rewrite a board's BOARD.json on disk. Best-effort — never raises.

    Always writes (even an empty snapshot when the board has 0 live rows — a cleared
    board must reflect as empty, not stale). Returns True on a successful write, False
    when the path is unresolvable or the write failed for any reason.
    """
    path = board_mirror_path(board, scope, project_root)
    if path is None:
        return False
    tmp_path = path.with_suffix(".tmp")
    try:
        snapshot = serialize_board(conn, board, scope)
        payload = json.dumps(snapshot, indent=2, ensure_ascii=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
            f.write("\n")
        os.replace(tmp_path, path)
        return True
    except Exception:
        logger.debug(
            "write_board_mirror failed for board=%s scope=%s", board, scope, exc_info=True
        )
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def export_project_boards(conn: sqlite3.Connection, project_root: str | None) -> int:
    """Export every mirror-able board for *project_root*. Returns the count written.

    Matches distinct (board, scope) pairs already present in comms_messages (including
    scopes whose rows are now all soft-deleted, so a cleared board's mirror still gets
    refreshed to empty) to their disk home: the project board (scope == the normalized
    project_root) and each feature board whose ``pathly/features/<feat>/`` directory
    already exists on disk. P0 has no project_root column on feature rows, so
    dir-existence is the resolution rule — a same-named feature directory that happens
    to exist under an unrelated root would be (mis)matched too; that cross-project
    ambiguity is deferred to P1 (marked * in the SPEC), not solved here. Also exports
    the global board once per call.
    """
    root = _norm_project_root(project_root)
    if not root:
        return 0

    written = 0
    pairs = conn.execute(
        "SELECT DISTINCT board, scope FROM comms_messages WHERE board IN ('project', 'feature')"
    ).fetchall()

    features_dir = Path(root) / "pathly" / "features"
    for row in pairs:
        board, scope = row["board"], row["scope"]
        if not scope:
            continue
        if board == "project":
            if scope != root:
                continue
        elif not (features_dir / scope).is_dir():
            continue
        if write_board_mirror(conn, board, scope, root):
            written += 1

    if write_board_mirror(conn, "global", "global", None):
        written += 1

    return written


def backfill_board_mirrors(conn: sqlite3.Connection) -> None:
    """Idempotent startup pass: export every project_root ever seen in run_history,
    then refresh the global board once more so it is written even when run_history is
    empty (e.g. a fresh install with only global-board posts). Best-effort — mirrors
    the invocation-projection backfill wiring exactly; never raises.
    """
    try:
        roots = conn.execute("SELECT DISTINCT project_root FROM run_history").fetchall()
        for row in roots:
            root = row["project_root"]
            if root:
                export_project_boards(conn, root)
        write_board_mirror(conn, "global", "global", None)
    except Exception:
        logger.debug("backfill_board_mirrors failed", exc_info=True)
