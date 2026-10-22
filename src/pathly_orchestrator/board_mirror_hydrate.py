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
from collections.abc import Callable
from pathlib import Path

from pathly_orchestrator.db.connection import _get_write_lock
from pathly_orchestrator.db.migrations_provenance import add_comms_provenance
from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact_row
from pathly_orchestrator.db.queries.comms_messages import (
    get_all_messages,
    insert_message_row,
)

logger = logging.getLogger("pathly.board_mirror")


def _belongs(msg: object, board: str, scope: str) -> bool:
    """True when a snapshot row is a row of the board its file was written for.

    The file's own ``board``/``scope`` keys are not read: they are as unverified as the rows.
    The row's scope is compared exactly: ``hydrate_project`` hands over the normalised project
    root and the exporter writes that spelling into every row, so a row that spells its root
    another way would be stored under a scope no board read asks for. A row whose ``id`` is not
    a string with something in it after stripping is not one an export wrote (a blank id would
    be a blank primary key).
    """
    return (
        isinstance(msg, dict)
        and isinstance(msg.get("id"), str)
        and bool(msg["id"].strip())
        and msg.get("board") == board
        and msg.get("scope") == scope
    )


def _entries(snapshot: dict, key: str) -> list:
    """The list the snapshot holds under *key*; a value that is not a list is no entries."""
    found = snapshot.get(key)
    return found if isinstance(found, list) else []


def hydrate_board(conn: sqlite3.Connection, board: str, scope: str, path: Path) -> bool:
    """Import *path* (a BOARD.json snapshot) into the DB for (board, scope).

    DB stays authoritative: if ``get_all_messages`` already returns rows for this
    (board, scope), this is a no-op (returns False) — an existing board is NEVER
    overwritten by a stale or divergent mirror. Otherwise the snapshot's message rows of this
    board, and the artifacts of those rows, are inserted (idempotent; a row keeps every column
    it names but ``binding`` and ``author_source``, see below) and each inserted message is
    best-effort re-embedded — the rows landing in the DB are hydration's whole value, so a
    missing/broken embedder must never block or fail it. Rows that carry no ``author_source``
    (a pre-upgrade snapshot) are then labelled ``legacy``. Never raises: a file that is not a
    JSON object returns False, and an entry that is not what an export writes (a row that is
    no object, an ``id`` that is blank or not a string, a ``message_id`` that is not a string,
    a list that is not a list) is left out, not fatal to the file or to the boards after it.

    Nothing in the file is verified (chief-agent 16): a message row whose ``board`` and
    ``scope`` are not this file's is left out, and the rows that are kept are stored with
    ``binding = 0`` and no verified author stamp (``comms_hydrate._unverified``). A standing
    order does not survive a fresh clone: the chief posts it again.

    What counts is what is in the database once the rows went in (chief-agent 20): a row whose
    id already belongs to a message of another board is not inserted (the insert is a no-op),
    so an artifact is inserted, and a message re-embedded, only for a row that is in the
    database under this board and scope. Returns True only when at least one row of the file is
    there; a file that adds nothing (every row names another scope, as in a clone at another
    path) returns False, so ``hydrate_project`` lists its scope under ``skipped``.
    """
    try:
        if get_all_messages(conn, board, scope):
            return False
        if not path.exists():
            return False
        # pathly:allow-mirror-read: fresh-clone SEED import — BOARD.json snapshot into an empty DB board
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("hydrate_board failed to read %s", path, exc_info=True)
        return False

    if not isinstance(snapshot, dict):
        logger.debug("hydrate_board: %s is not a JSON object", path)
        return False

    for msg in _entries(snapshot, "messages"):
        if _belongs(msg, board, scope):
            insert_message_row(conn, msg)
    landed = {m["id"] for m in get_all_messages(conn, board, scope)}
    messages = [
        m
        for m in _entries(snapshot, "messages")
        if _belongs(m, board, scope) and m["id"] in landed
    ]
    if not messages:
        logger.debug("hydrate_board: %s adds no row to %s/%s", path, board, scope)
        return False
    artifacts = [
        a
        for a in _entries(snapshot, "artifacts")
        if isinstance(a, dict)
        and isinstance(a.get("message_id"), str)
        and a["message_id"] in landed
    ]
    for art in artifacts:
        insert_artifact_row(conn, art)

    # A snapshot exported before the provenance columns existed has no author_* keys, so
    # its rows landed with a NULL author_source (which no read wall treats as `none`).
    # The startup backfill labels them `legacy`; run it now rather than at the next start.
    try:
        with _get_write_lock(conn):
            add_comms_provenance(conn)
    except Exception:
        logger.debug("hydrate_board: provenance backfill failed", exc_info=True)

    _embed_fn: Callable[[str, str, str], None] | None = None
    try:
        from pathly_orchestrator.runner.embeddings import embed_artifact_async

        _embed_fn = embed_artifact_async
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
