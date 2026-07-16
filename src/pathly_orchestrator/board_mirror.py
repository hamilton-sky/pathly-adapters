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
import threading
import time
from pathlib import Path

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_artifacts import list_artifacts_for_messages
from pathly_orchestrator.db.queries.comms_messages import get_all_messages
from pathly_orchestrator.db.queries.run_history import latest_project_root_for_feature
from pathly_orchestrator.storage_paths import _RESERVED_TOPICS

logger = logging.getLogger("pathly.board_mirror")

# Debounce window for the live mirror flusher — coalesces a burst of board writes
# (e.g. a goal run posting many task updates) into a single BOARD.json rewrite.
DEBOUNCE_SECONDS = 0.5


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
    # Defensive: never mirror a feature board whose scope is a reserved structural name
    # (e.g. a stray 'project'/'global' literal from a mis-scoped write). It would create
    # pathly/features/<reserved>/, and that dir's UI section id collides with the real
    # project/global board section → duplicate React key → flicker.
    if scope in _RESERVED_TOPICS:
        return None
    return Path(root) / "pathly" / "features" / scope / "BOARD.json"


def board_from_scope(scope: str) -> str:
    """Derive the board kind from a DB scope string. Scope conventions: the global board
    is the literal 'global'; a project board's scope is a normalized absolute path (has a
    '/'); a feature board's scope is a bare slug (no '/')."""
    if scope == "global":
        return "global"
    if "/" in scope:
        return "project"
    return "feature"


def resolve_project_root(
    conn: sqlite3.Connection, board: str, scope: str
) -> str | None:
    """The project_root a (board, scope) mirror belongs to. global -> None (its mirror
    lives in ~/.pathly, no root); project -> the scope itself (it IS the root); feature ->
    the run_history lookup (★ — supersedes the SPEC's new-column idea; run_history already
    maps feature->project_root). None when a feature has no run history yet: it can't be
    placed on the live path, but the startup backfill's on-disk scan still catches it.
    """
    if board == "global":
        return None
    if board == "project":
        return _norm_project_root(scope)
    return _norm_project_root(latest_project_root_for_feature(conn, scope))


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
        payload = json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n"
        # Change-guard: skip the rewrite (and its git churn) when the board is byte-
        # identical to what's already on disk. The live hook fires on transient
        # lifecycle broadcasts too, so most flushes carry no real content change.
        if path.exists():
            try:
                if path.read_text(encoding="utf-8") == payload:
                    return True
            except Exception:
                pass  # unreadable existing file — fall through and rewrite it
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp_path, path)
        return True
    except Exception:
        logger.debug(
            "write_board_mirror failed for board=%s scope=%s",
            board,
            scope,
            exc_info=True,
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


# ── Live mirror: debounced write hook (P1) ───────────────────────────────────
# The single hook is http_server/sse._broadcast_comms (called after every board
# write); it calls mark_board_dirty_by_scope. A background flusher coalesces a
# burst of writes to one board into a single BOARD.json rewrite.

_dirty: set[tuple[str, str]] = set()
_dirty_lock = threading.Lock()
_flusher_started = False


def flush_dirty(conn: sqlite3.Connection) -> int:
    """Drain the dirty (board, scope) set and rewrite each board's mirror. Synchronous
    and best-effort — the unit the background thread AND tests call. Returns the count of
    mirrors written (a no-op change-guard hit still counts as written/True)."""
    with _dirty_lock:
        pending = list(_dirty)
        _dirty.clear()
    written = 0
    for board, scope in pending:
        try:
            root = resolve_project_root(conn, board, scope)
            if write_board_mirror(conn, board, scope, root):
                written += 1
        except Exception:
            logger.debug(
                "flush_dirty item failed board=%s scope=%s", board, scope, exc_info=True
            )
    return written


def _flusher_loop() -> None:
    """Daemon loop: every DEBOUNCE_SECONDS, flush the dirty set. Uses its OWN per-thread
    get_db() connection (sqlite connections are check_same_thread=True — a connection from
    another thread cannot be reused). Never dies."""
    while True:
        try:
            time.sleep(DEBOUNCE_SECONDS)
            if _dirty:
                flush_dirty(get_db())
        except Exception:
            logger.debug("board-mirror flusher tick failed", exc_info=True)


def mark_board_dirty(board: str, scope: str) -> None:
    """Queue a board for a debounced mirror rewrite, lazily starting the flusher thread."""
    global _flusher_started
    with _dirty_lock:
        _dirty.add((board, scope))
        if not _flusher_started:
            _flusher_started = True
            threading.Thread(
                target=_flusher_loop, name="board-mirror-flusher", daemon=True
            ).start()


def mark_board_dirty_by_scope(scope: str) -> None:
    """Hook entry point: derive the board from the scope and queue it. Best-effort — never
    raises into the caller (the SSE broadcast)."""
    try:
        mark_board_dirty(board_from_scope(scope), scope)
    except Exception:
        logger.debug("mark_board_dirty_by_scope failed scope=%s", scope, exc_info=True)


# ── Hydration: import BOARD.json mirrors back into the DB (P2) ──────────────────
# hydrate_board/hydrate_project live in board_mirror_hydrate.py (keeps this file under
# the project's 400-line cap); re-exported here for the conventional import path.
from .board_mirror_hydrate import hydrate_board, hydrate_project  # noqa: E402, F401
