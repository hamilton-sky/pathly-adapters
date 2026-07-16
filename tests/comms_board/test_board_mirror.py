"""Board disk-mirror P0 — path resolver, atomic exporter, idempotent backfill.

P0 is behavior-neutral, export-only: the DB stays the runtime system of record and
these tests only exercise the DB->disk export path (board_mirror_path, serialize_board,
write_board_mirror, export_project_boards, backfill_board_mirrors). No live write hook
(P1) and no hydration back into the DB (P2) exist yet.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pathly_orchestrator.board_mirror import (
    backfill_board_mirrors,
    board_mirror_path,
    export_project_boards,
    serialize_board,
    write_board_mirror,
)
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact
from pathly_orchestrator.db.queries.comms_messages import post_message, soft_delete_message
from pathly_orchestrator.db.queries.run_history import upsert_run


# ── board_mirror_path ──────────────────────────────────────────────────────────────


def test_board_mirror_path_global_ignores_project_root(tmp_path):
    with_root = board_mirror_path("global", "global", str(tmp_path / "somewhere"))
    without_root = board_mirror_path("global", "global", None)
    assert with_root == without_root == Path.home() / ".pathly" / "global" / "BOARD.json"


def test_board_mirror_path_project(tmp_path):
    root = str(tmp_path / "proj")
    p = board_mirror_path("project", "ignored-for-project", root)
    assert p == Path(root) / "pathly" / "project" / "BOARD.json"


def test_board_mirror_path_project_none_without_root():
    assert board_mirror_path("project", "whatever", None) is None


def test_board_mirror_path_feature(tmp_path):
    root = str(tmp_path / "proj")
    p = board_mirror_path("feature", "my-feature", root)
    assert p == Path(root) / "pathly" / "features" / "my-feature" / "BOARD.json"


def test_board_mirror_path_feature_none_without_root():
    assert board_mirror_path("feature", "my-feature", None) is None


def test_board_mirror_path_unknown_board_returns_none(tmp_path):
    assert board_mirror_path("bogus", "x", str(tmp_path)) is None


def test_board_mirror_path_normalizes_root(tmp_path):
    root_dir = tmp_path / "proj"
    clean_root = str(root_dir).replace("\\", "/").rstrip("/")
    messy_root = clean_root.replace("/", "\\") + "\\"  # backslashes + trailing slash
    p_clean = board_mirror_path("project", "s", clean_root)
    p_messy = board_mirror_path("project", "s", messy_root)
    assert p_clean == p_messy


# ── serialize_board ─────────────────────────────────────────────────────────────────


def test_serialize_board_shape_and_content():
    conn = get_db()
    post_message(conn, board="feature", scope="s1", from_agent="human", type="nudge", text="hello")
    data = serialize_board(conn, "feature", "s1")
    assert data["board"] == "feature"
    assert data["scope"] == "s1"
    assert data["version"] == 1
    assert isinstance(data["messages"], list) and len(data["messages"]) == 1
    assert data["messages"][0]["text"] == "hello"
    assert isinstance(data["artifacts"], list) and data["artifacts"] == []


def test_serialize_board_excludes_soft_deleted():
    conn = get_db()
    mid_keep = post_message(
        conn, board="feature", scope="s2", from_agent="human", type="nudge", text="keep"
    )
    mid_drop = post_message(
        conn, board="feature", scope="s2", from_agent="human", type="nudge", text="drop"
    )
    result = soft_delete_message(conn, mid_drop, force=True)
    assert result == "deleted"

    data = serialize_board(conn, "feature", "s2")
    ids = [m["id"] for m in data["messages"]]
    assert mid_keep in ids
    assert mid_drop not in ids


def test_serialize_board_sorted_by_ts_then_id():
    conn = get_db()
    mid_a = post_message(conn, board="feature", scope="s3", from_agent="human", type="nudge", text="a")
    mid_b = post_message(conn, board="feature", scope="s3", from_agent="human", type="nudge", text="b")
    # Force a deterministic order regardless of insertion order / wall-clock timing.
    conn.execute("UPDATE comms_messages SET ts=? WHERE id=?", ("2026-01-01T00:00:02Z", mid_a))
    conn.execute("UPDATE comms_messages SET ts=? WHERE id=?", ("2026-01-01T00:00:01Z", mid_b))
    conn.commit()

    data = serialize_board(conn, "feature", "s3")
    assert [m["id"] for m in data["messages"]] == [mid_b, mid_a]


def test_serialize_board_includes_linked_artifacts():
    conn = get_db()
    mid = post_message(conn, board="feature", scope="s4", from_agent="human", type="artifact", text="art")
    insert_artifact(
        conn, message_id=mid, path="pathly/features/s4/NOTES.md", type="md", title="Notes"
    )
    data = serialize_board(conn, "feature", "s4")
    assert len(data["artifacts"]) == 1
    assert data["artifacts"][0]["path"] == "pathly/features/s4/NOTES.md"
    assert data["artifacts"][0]["message_id"] == mid


# ── write_board_mirror ───────────────────────────────────────────────────────────────


def test_write_board_mirror_writes_valid_json(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj1")
    post_message(conn, board="feature", scope="featx", from_agent="human", type="nudge", text="hello")

    ok = write_board_mirror(conn, "feature", "featx", root)
    assert ok is True

    path = Path(root) / "pathly" / "features" / "featx" / "BOARD.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["board"] == "feature"
    assert data["scope"] == "featx"
    assert data["version"] == 1
    assert len(data["messages"]) == 1
    assert data["messages"][0]["text"] == "hello"


def test_write_board_mirror_empty_snapshot_for_no_rows(tmp_path):
    conn = get_db()
    root = str(tmp_path / "proj2")

    ok = write_board_mirror(conn, "feature", "emptyfeat", root)
    assert ok is True

    path = Path(root) / "pathly" / "features" / "emptyfeat" / "BOARD.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["messages"] == []
    assert data["artifacts"] == []


def test_write_board_mirror_unresolvable_returns_false():
    conn = get_db()
    assert write_board_mirror(conn, "feature", "featx", None) is False
    assert write_board_mirror(conn, "project", "ignored", None) is False


# ── export_project_boards ───────────────────────────────────────────────────────────


def test_export_project_boards_writes_existing_dirs_only(tmp_path):
    conn = get_db()
    root_dir = tmp_path / "proj3"
    root = str(root_dir)
    norm_root = root.replace("\\", "/").rstrip("/")

    # Project board: its scope MUST equal the normalized project_root.
    post_message(conn, board="project", scope=norm_root, from_agent="human", type="nudge", text="hi project")
    # Feature board A: its directory exists on disk.
    (root_dir / "pathly" / "features" / "featA").mkdir(parents=True)
    post_message(conn, board="feature", scope="featA", from_agent="human", type="nudge", text="hi A")
    # Feature board B: no directory on disk -> must NOT be exported.
    post_message(conn, board="feature", scope="featB", from_agent="human", type="nudge", text="hi B")

    count = export_project_boards(conn, root)

    project_file = root_dir / "pathly" / "project" / "BOARD.json"
    featA_file = root_dir / "pathly" / "features" / "featA" / "BOARD.json"
    featB_file = root_dir / "pathly" / "features" / "featB" / "BOARD.json"
    global_file = Path.home() / ".pathly" / "global" / "BOARD.json"

    assert project_file.exists()
    assert featA_file.exists()
    assert not featB_file.exists()
    assert global_file.exists()
    assert count == 3  # project + featA + global


def test_export_project_boards_returns_zero_for_no_project_root():
    conn = get_db()
    assert export_project_boards(conn, "") == 0
    assert export_project_boards(conn, None) == 0


def test_export_project_boards_normalizes_root_for_scope_match(tmp_path):
    conn = get_db()
    root_dir = tmp_path / "proj4"
    clean_root = str(root_dir).replace("\\", "/").rstrip("/")
    post_message(conn, board="project", scope=clean_root, from_agent="human", type="nudge", text="hi")

    messy_root = str(root_dir) + os.sep  # OS-native trailing separator
    count = export_project_boards(conn, messy_root)

    project_file = root_dir / "pathly" / "project" / "BOARD.json"
    assert project_file.exists()
    assert count >= 1


# ── backfill_board_mirrors ──────────────────────────────────────────────────────────


def test_backfill_board_mirrors_exports_known_roots(tmp_path):
    conn = get_db()
    root_dir = tmp_path / "proj5"
    norm_root = str(root_dir).replace("\\", "/").rstrip("/")
    upsert_run(conn, norm_root, "featx", "run-1", "done")
    post_message(conn, board="project", scope=norm_root, from_agent="human", type="nudge", text="hi")

    backfill_board_mirrors(conn)

    project_file = root_dir / "pathly" / "project" / "BOARD.json"
    global_file = Path.home() / ".pathly" / "global" / "BOARD.json"
    assert project_file.exists()
    assert global_file.exists()


def test_backfill_board_mirrors_handles_empty_tables():
    conn = get_db()  # fresh test DB: run_history and comms_messages both empty
    backfill_board_mirrors(conn)  # must not raise
    global_file = Path.home() / ".pathly" / "global" / "BOARD.json"
    assert global_file.exists()
