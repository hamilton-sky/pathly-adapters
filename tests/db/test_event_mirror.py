"""EventMirror — DB -> disk export for EVENTS.jsonl (state-one-authority, additive P1a).

Behavior-neutral, export-only: fsm_events stays the runtime system of record and these
tests exercise only the DB -> disk export path (event_mirror_path, serialize_events,
write_event_mirror's change-guard, flush_dirty, backfill_event_mirrors) plus the live
wire-in from eventlog.append_event. The background flusher thread and real sleeps are NOT
exercised — tests populate the dirty set directly / drain via flush_dirty synchronously so
they stay deterministic, mirroring tests/comms_board/test_board_mirror_live.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pathly_orchestrator.event_mirror as em
from pathly_orchestrator import eventlog
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.fsm_events import append_event as db_append_event
from pathly_orchestrator.event_mirror import (
    backfill_event_mirrors,
    event_mirror_path,
    flush_dirty,
    serialize_events,
    write_event_mirror,
)


def _reset_dirty() -> None:
    with em._dirty_lock:
        em._dirty.clear()


def _feature_dir(tmp_path: Path, feature: str) -> Path:
    """A flat feature dir <root>/pathly/features/<feature> (created)."""
    d = tmp_path / "proj" / "pathly" / "features" / feature
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── event_mirror_path ─────────────────────────────────────────────────────────


def test_event_mirror_path_appends_events_jsonl(tmp_path):
    d = tmp_path / "pathly" / "features" / "feat"
    assert event_mirror_path(d) == d / "EVENTS.jsonl"


def test_event_mirror_path_none_for_empty():
    assert event_mirror_path("") is None
    assert event_mirror_path(None) is None


# ── serialize_events (matches read_events, seq-ordered, empty -> "") ────────────


def test_serialize_events_matches_db_rows_in_seq_order(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    db_append_event(conn, root, "feat-ser", {"type": "FSM_INIT", "state": "PLANNING"})
    db_append_event(
        conn,
        root,
        "feat-ser",
        {"type": "STATE_TRANSITION", "from": "PLANNING", "to": "BUILDING"},
    )

    body = serialize_events(conn, root, "feat-ser")
    lines = body.splitlines()
    assert len(lines) == 2
    first, second = json.loads(lines[0]), json.loads(lines[1])
    assert first["type"] == "FSM_INIT" and second["type"] == "STATE_TRANSITION"
    # seq is the ordering key and must be present + ascending (it IS what read_events returns).
    assert first["seq"] < second["seq"]


def test_serialize_events_empty_for_no_events(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    assert serialize_events(conn, root, "never-logged") == ""


# ── write_event_mirror: content, change-guard, no-events skip ───────────────────


def test_write_event_mirror_writes_file_matching_db(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    fdir = _feature_dir(tmp_path, "feat-write")
    db_append_event(conn, root, "feat-write", {"type": "FSM_INIT", "state": "PLANNING"})

    assert write_event_mirror(conn, fdir, root, "feat-write") is True
    path = fdir / "EVENTS.jsonl"
    assert path.exists()
    assert path.read_text(encoding="utf-8") == serialize_events(
        conn, root, "feat-write"
    )


def test_write_event_mirror_change_guard_skips_identical(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    fdir = _feature_dir(tmp_path, "feat-guard")
    db_append_event(conn, root, "feat-guard", {"type": "FSM_INIT", "state": "PLANNING"})
    path = fdir / "EVENTS.jsonl"

    assert write_event_mirror(conn, fdir, root, "feat-guard") is True
    first = path.read_text(encoding="utf-8")
    mtime1 = path.stat().st_mtime_ns

    # No new events -> change-guard returns True WITHOUT rewriting (mtime unchanged).
    assert write_event_mirror(conn, fdir, root, "feat-guard") is True
    assert path.read_text(encoding="utf-8") == first
    assert path.stat().st_mtime_ns == mtime1


def test_write_event_mirror_skips_when_no_events(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    fdir = _feature_dir(tmp_path, "feat-none")
    # No events for this feature -> no spurious empty EVENTS.jsonl planted.
    assert write_event_mirror(conn, fdir, root, "feat-none") is False
    assert not (fdir / "EVENTS.jsonl").exists()


# ── flush_dirty (the mark -> flush path the hook + flusher drive) ───────────────


def test_flush_dirty_writes_a_marked_feature(tmp_path):
    _reset_dirty()
    conn = get_db()
    root = str(tmp_path / "proj")
    fdir = _feature_dir(tmp_path, "feat-flush")
    db_append_event(conn, root, "feat-flush", {"type": "FSM_INIT", "state": "PLANNING"})

    with em._dirty_lock:
        em._dirty.add((str(fdir), root, "feat-flush"))
    written = flush_dirty(conn)

    assert written == 1
    assert (fdir / "EVENTS.jsonl").exists()
    assert len(em._dirty) == 0  # drained
    _reset_dirty()


# ── backfill_event_mirrors (startup pass over fsm_events, flat-dir resolution) ──


def test_backfill_writes_events_for_feature_with_db_history_no_file(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    fdir = _feature_dir(tmp_path, "feat-backfill")  # dir exists, no EVENTS.jsonl yet
    db_append_event(
        conn, root, "feat-backfill", {"type": "FSM_INIT", "state": "PLANNING"}
    )
    db_append_event(
        conn,
        root,
        "feat-backfill",
        {"type": "STATE_TRANSITION", "from": "PLANNING", "to": "BUILDING"},
    )
    path = fdir / "EVENTS.jsonl"
    assert not path.exists()

    backfill_event_mirrors(conn)

    assert path.exists()
    assert path.read_text(encoding="utf-8") == serialize_events(
        conn, root, "feat-backfill"
    )


def test_backfill_skips_feature_without_dir_on_disk(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    # DB history but NO on-disk dir -> flat-dir resolution finds nothing, no crash, no file.
    db_append_event(
        conn, root, "ghost-feature", {"type": "FSM_INIT", "state": "PLANNING"}
    )
    backfill_event_mirrors(conn)  # must not raise
    assert not (
        Path(root) / "pathly" / "features" / "ghost-feature" / "EVENTS.jsonl"
    ).exists()


# ── live wire-in: eventlog.append_event enqueues + exports (additive) ───────────


def test_eventlog_append_event_exports_via_mirror(tmp_path):
    _reset_dirty()
    conn = get_db()
    fdir = _feature_dir(tmp_path, "feat-live")

    eventlog.append_event(str(fdir), {"type": "FSM_INIT", "state": "PLANNING"})
    # Drain synchronously (the background flusher may also fire; flush_dirty is idempotent).
    flush_dirty(conn)

    path = fdir / "EVENTS.jsonl"
    assert path.exists()
    # Content is the DB projection — the export, not an agent-side append.
    project_root = eventlog._project_root_of(fdir.resolve())
    assert path.read_text(encoding="utf-8") == serialize_events(
        conn, project_root, "feat-live"
    )
    body = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert body["type"] == "FSM_INIT"
    _reset_dirty()
