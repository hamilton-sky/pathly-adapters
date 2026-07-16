"""Board disk-mirror P1 — live debounced mirror.

Covers the PURE/synchronous surface: board_from_scope, resolve_project_root (the ★
run_history resolution), write_board_mirror's change-guard, and flush_dirty (the unit
the background flusher drains). The background thread and real sleeps are deliberately
NOT exercised — tests populate the module dirty set directly and call flush_dirty, so
they stay deterministic. The hook (sse._broadcast_comms -> mark_board_dirty_by_scope)
is exactly this mark->flush path.
"""

from __future__ import annotations

import pathly_orchestrator.board_mirror as bm
from pathly_orchestrator.board_mirror import (
    board_from_scope,
    board_mirror_path,
    flush_dirty,
    resolve_project_root,
    write_board_mirror,
)
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_messages import post_message
from pathly_orchestrator.db.queries.run_history import upsert_run


def _reset_dirty() -> None:
    with bm._dirty_lock:
        bm._dirty.clear()


# ── board_from_scope ─────────────────────────────────────────────────────────


def test_board_from_scope_global():
    assert board_from_scope("global") == "global"


def test_board_from_scope_project_is_a_path():
    assert board_from_scope("C:/Users/Yafit/proj") == "project"


def test_board_from_scope_feature_is_a_slug():
    assert board_from_scope("my-feature") == "feature"


# ── resolve_project_root ─────────────────────────────────────────────────────


def test_resolve_project_root_project_is_the_scope():
    conn = get_db()
    assert resolve_project_root(conn, "project", "C:/Users/Yafit/proj") == "C:/Users/Yafit/proj"


def test_resolve_project_root_project_normalizes():
    conn = get_db()
    assert resolve_project_root(conn, "project", "C:\\Users\\Yafit\\proj\\") == "C:/Users/Yafit/proj"


def test_resolve_project_root_global_is_none():
    conn = get_db()
    assert resolve_project_root(conn, "global", "global") is None


def test_resolve_project_root_feature_from_run_history():
    conn = get_db()
    upsert_run(conn, project_root="C:/Users/Yafit/proj", feature="feat-x", run_id="r1", status="done")
    assert resolve_project_root(conn, "feature", "feat-x") == "C:/Users/Yafit/proj"


def test_resolve_project_root_feature_missing_is_none():
    conn = get_db()
    assert resolve_project_root(conn, "feature", "never-ran-feature") is None


# ── change-guard ─────────────────────────────────────────────────────────────


def test_write_board_mirror_change_guard_skips_identical(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj")
    scope = root.replace("\\", "/").rstrip("/")
    post_message(conn, board="project", scope=scope, from_agent="human", type="nudge", text="hi")
    path = board_mirror_path("project", scope, root)

    assert write_board_mirror(conn, "project", scope, root) is True
    assert path is not None and path.exists()
    first = path.read_text(encoding="utf-8")
    mtime1 = path.stat().st_mtime_ns

    # DB unchanged -> the change-guard returns True WITHOUT rewriting (mtime unchanged).
    assert write_board_mirror(conn, "project", scope, root) is True
    assert path.read_text(encoding="utf-8") == first
    assert path.stat().st_mtime_ns == mtime1


# ── flush_dirty (the mark->flush path the flusher and the hook drive) ─────────


def test_flush_dirty_writes_a_marked_project_board(tmp_path):
    _reset_dirty()
    conn = get_db()
    root = str(tmp_path / "proj").replace("\\", "/").rstrip("/")
    post_message(conn, board="project", scope=root, from_agent="human", type="nudge", text="hi")

    with bm._dirty_lock:
        bm._dirty.add(("project", root))
    written = flush_dirty(conn)

    path = board_mirror_path("project", root, root)
    assert written == 1
    assert path is not None and path.exists()
    assert len(bm._dirty) == 0  # drained
    _reset_dirty()


def test_flush_dirty_resolves_feature_root_via_run_history(tmp_path):
    _reset_dirty()
    conn = get_db()
    root = str(tmp_path / "proj").replace("\\", "/").rstrip("/")
    post_message(conn, board="feature", scope="feat-live", from_agent="human", type="nudge", text="hi")
    upsert_run(conn, project_root=root, feature="feat-live", run_id="r1", status="done")

    with bm._dirty_lock:
        bm._dirty.add(("feature", "feat-live"))
    written = flush_dirty(conn)

    path = board_mirror_path("feature", "feat-live", root)
    assert written == 1
    assert path is not None and path.exists()
    _reset_dirty()
