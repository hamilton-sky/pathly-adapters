"""
EventMirror — export a feature's fsm_events log to disk as EVENTS.jsonl.

The central DB (``~/.pathly/pathly.db``, table ``fsm_events``) stays the runtime system
of record; this module writes a synchronized, git-trackable JSONL snapshot of each
feature's event stream next to the feature on disk — the same DB -> disk export pattern
``board_mirror`` uses for ``BOARD.json`` and ``eventlog._write_state_db`` uses for
``STATE.json``: temp file + atomic replace, change-guarded, debounced.

Unlike ``board_mirror`` (keyed by ``(board, scope)``), this exporter is keyed by the
already-resolved ``feature_dir`` — the same ``Path`` ``eventlog.append_event`` computes for
the DB write — so debug/explore/goal runs (which live under ``pathly/debugs``,
``pathly/explorations``, ``.../goals/<slug>``) export to their real on-disk home, not a
reconstructed ``pathly/features/<name>`` guess. This is the one deliberate design divergence
from ``board_mirror``.

Pure DB -> disk export, never the other direction — no live write hook mutating the DB and
no hydration/import back into it. Reads events via ``db.queries.fsm_events`` directly and
must NOT import ``eventlog`` (which imports this module's hook), to avoid a cycle.
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
from pathly_orchestrator.db.queries.fsm_events import read_events

logger = logging.getLogger("pathly.event_mirror")

# Debounce window — coalesces a burst of event appends (e.g. a stage writing
# STATE_TRANSITION + AGENT_DONE + BILLING_UPDATE in quick succession) into a single
# EVENTS.jsonl rewrite. Matches board_mirror.DEBOUNCE_SECONDS.
DEBOUNCE_SECONDS = 0.5


def event_mirror_path(feature_dir: "str | Path | None") -> Path | None:
    """Resolve the on-disk EVENTS.jsonl path for an already-resolved feature_dir.

    None when feature_dir is empty. The dir itself is the DB write's resolved
    ``feature_dir`` (``eventlog.append_event``), so no reconstruction/guessing is needed —
    the file lands next to the feature wherever it really lives on disk.
    """
    if not feature_dir:
        return None
    return Path(feature_dir) / "EVENTS.jsonl"


def serialize_events(conn: sqlite3.Connection, project_root: str, feature: str) -> str:
    """The EVENTS.jsonl body for (project_root, feature): every fsm_events row in seq order,
    one compact JSON object per line (exactly what ``read_events`` returns — the canonical
    event reader — including its ``seq`` ordering key).

    Returns "" when the feature has no events. Events are append-only and never cleared, so
    an empty log means "nothing logged yet", not "cleared" — the caller skips the write
    rather than plant a spurious empty file (the second deliberate divergence from
    ``board_mirror``, which writes empty snapshots for cleared boards).
    """
    events = read_events(conn, project_root, feature)
    if not events:
        return ""
    return "".join(json.dumps(e) + "\n" for e in events)


def write_event_mirror(
    conn: sqlite3.Connection,
    feature_dir: "str | Path",
    project_root: str,
    feature: str,
) -> bool:
    """Atomically rewrite a feature's EVENTS.jsonl on disk. Best-effort — never raises.

    Returns False when the path is unresolvable or the feature has no events yet; True on a
    successful write (or a change-guard no-op). Change-guarded: a byte-identical file is left
    untouched — no git churn, stable mtime — because the debounced hook fires on every append
    and most flushes re-derive content that is already on disk.
    """
    path = event_mirror_path(feature_dir)
    if path is None:
        return False
    tmp_path = path.with_suffix(".tmp")
    try:
        payload = serialize_events(conn, project_root, feature)
        if not payload:
            return False
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
            "write_event_mirror failed for feature=%s dir=%s",
            feature,
            feature_dir,
            exc_info=True,
        )
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False


def backfill_event_mirrors(conn: sqlite3.Connection) -> None:
    """Idempotent startup pass: export the EVENTS.jsonl for every (project_root, feature) in
    fsm_events whose flat feature dir (``<project_root>/pathly/features/<feature>``) exists on
    disk. Best-effort — mirrors ``backfill_board_mirrors``' wiring; never raises.

    Nested/goal runs — whose real dir cannot be reconstructed from the (root, basename) key
    alone — are covered by the live ``mark_event_dirty`` hook going forward, not this backfill.
    Same dir-existence resolution + deferred cross-project ambiguity tradeoff ``board_mirror``
    documents for its feature boards.
    """
    try:
        rows = conn.execute(
            "SELECT DISTINCT project_root, feature FROM fsm_events"
        ).fetchall()
        for row in rows:
            project_root = row["project_root"]
            feature = row["feature"]
            if not project_root or not feature:
                continue
            feature_dir = Path(project_root) / "pathly" / "features" / feature
            if feature_dir.is_dir():
                write_event_mirror(conn, feature_dir, project_root, feature)
    except Exception:
        logger.debug("backfill_event_mirrors failed", exc_info=True)


# ── Live mirror: debounced write hook ─────────────────────────────────────────
# The single hook is eventlog.append_event (the one append chokepoint); it calls
# mark_event_dirty(feature_dir, project_root, feature) right after the DB append. A
# background flusher coalesces a burst of appends to one feature into a single rewrite.
# Keyed by (feature_dir, project_root, feature) so the resolved on-disk home is carried
# through — board_mirror re-derives the root in flush_dirty, but here append_event already
# holds the exact feature_dir, so we thread all three through and never guess.

_dirty: set[tuple[str, str, str]] = set()
_dirty_lock = threading.Lock()
_flusher_started = False


def flush_dirty(conn: sqlite3.Connection) -> int:
    """Drain the dirty set and rewrite each feature's EVENTS.jsonl. Synchronous and
    best-effort — the unit the background thread AND tests call. Returns the count written
    (a no-op change-guard hit still counts as written/True; a no-events feature does not).
    """
    with _dirty_lock:
        pending = list(_dirty)
        _dirty.clear()
    written = 0
    for feature_dir, project_root, feature in pending:
        try:
            if write_event_mirror(conn, feature_dir, project_root, feature):
                written += 1
        except Exception:
            logger.debug(
                "flush_dirty item failed feature=%s dir=%s",
                feature,
                feature_dir,
                exc_info=True,
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
            logger.debug("event-mirror flusher tick failed", exc_info=True)


def mark_event_dirty(
    feature_dir: "str | Path", project_root: str, feature: str
) -> None:
    """Queue a feature's event log for a debounced EVENTS.jsonl rewrite, lazily starting the
    flusher thread. Best-effort — never raises into the caller (``eventlog.append_event``).
    """
    global _flusher_started
    try:
        key = (str(feature_dir), str(project_root), str(feature))
    except Exception:
        return
    with _dirty_lock:
        _dirty.add(key)
        if not _flusher_started:
            _flusher_started = True
            threading.Thread(
                target=_flusher_loop, name="event-mirror-flusher", daemon=True
            ).start()
