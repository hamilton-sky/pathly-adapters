"""Board disk-mirror P2 — hydration (import BOARD.json mirrors back into the DB).

Covers insert_message_row/insert_artifact_row (full-fidelity, filtered-column, idempotent
row inserts used only by hydration) and hydrate_board/hydrate_project (the DB-empty-only
import path). hydrate_board/hydrate_project are imported from board_mirror — the
conventional public surface (board_mirror_hydrate.py's functions are re-exported there) —
matching how http_server/blueprints/comms/hydrate.py imports them.
"""

from __future__ import annotations

import json

from pathly_orchestrator.board_mirror import hydrate_board, hydrate_project
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_artifacts import insert_artifact, insert_artifact_row
from pathly_orchestrator.db.queries.comms_messages import (
    get_all_messages,
    insert_message_row,
    post_message,
)


# ── insert_message_row ───────────────────────────────────────────────────────────


def test_insert_message_row_round_trip_preserves_all_fields():
    conn = get_db()
    mid = post_message(
        conn, board="feature", scope="s-rt1", from_agent="human", type="nudge", text="hello"
    )
    conn.execute(
        "UPDATE comms_messages SET status=?, read_by=?, acknowledged_by=?, ts=? WHERE id=?",
        ("resolved", '["human"]', '["agent"]', "2026-01-01T00:00:00Z", mid),
    )
    conn.commit()
    original = dict(
        conn.execute("SELECT * FROM comms_messages WHERE id=?", (mid,)).fetchone()
    )

    conn.execute("DELETE FROM comms_messages WHERE id=?", (mid,))
    conn.commit()
    assert conn.execute("SELECT * FROM comms_messages WHERE id=?", (mid,)).fetchone() is None

    insert_message_row(conn, original)

    restored = conn.execute("SELECT * FROM comms_messages WHERE id=?", (mid,)).fetchone()
    assert restored is not None
    assert dict(restored) == original


def test_insert_message_row_idempotent_on_id_collision():
    conn = get_db()
    mid = post_message(
        conn, board="feature", scope="s-rt3", from_agent="human", type="nudge", text="original"
    )
    row = dict(conn.execute("SELECT * FROM comms_messages WHERE id=?", (mid,)).fetchone())
    row["text"] = "would-be overwrite"

    insert_message_row(conn, row)  # id already exists -> INSERT OR IGNORE no-op

    current = conn.execute("SELECT text FROM comms_messages WHERE id=?", (mid,)).fetchone()
    assert current["text"] == "original"


def test_insert_message_row_filters_unknown_keys():
    conn = get_db()
    row = {
        "id": "msg-unknown-keys",
        "board": "feature",
        "scope": "s-rt4",
        "from_agent": "human",
        "to_agent": "*",
        "type": "nudge",
        "text": "hi",
        "ts": "2026-01-01T00:00:00Z",
        "some_future_snapshot_only_field": "should be dropped",
    }
    insert_message_row(conn, row)  # must not raise

    fetched = conn.execute(
        "SELECT * FROM comms_messages WHERE id=?", ("msg-unknown-keys",)
    ).fetchone()
    assert fetched is not None
    assert fetched["text"] == "hi"


def test_insert_message_row_empty_dict_is_a_noop():
    conn = get_db()
    insert_message_row(conn, {})  # must not raise
    insert_message_row(conn, None)  # must not raise


# ── insert_artifact_row ──────────────────────────────────────────────────────────


def test_insert_artifact_row_round_trip_preserves_all_fields():
    conn = get_db()
    mid = post_message(
        conn, board="feature", scope="s-rt2", from_agent="human", type="artifact", text="art"
    )
    aid = insert_artifact(
        conn,
        message_id=mid,
        path="pathly/features/s-rt2/NOTES.md",
        type="md",
        title="Notes",
        summary="a summary",
        token_count=42,
        created_by="human",
    )
    conn.execute(
        "UPDATE comms_artifacts SET last_edit_at=?, last_edit_by=?, version=?, supersedes=? "
        "WHERE id=?",
        ("2026-01-02T00:00:00Z", "human", 2, "old-id", aid),
    )
    conn.commit()
    original = dict(
        conn.execute("SELECT * FROM comms_artifacts WHERE id=?", (aid,)).fetchone()
    )

    conn.execute("DELETE FROM comms_artifacts WHERE id=?", (aid,))
    conn.commit()
    assert conn.execute("SELECT * FROM comms_artifacts WHERE id=?", (aid,)).fetchone() is None

    insert_artifact_row(conn, original)

    restored = conn.execute("SELECT * FROM comms_artifacts WHERE id=?", (aid,)).fetchone()
    assert restored is not None
    assert dict(restored) == original


def test_insert_artifact_row_idempotent_on_id_collision():
    conn = get_db()
    mid = post_message(
        conn, board="feature", scope="s-rt5", from_agent="human", type="artifact", text="art"
    )
    aid = insert_artifact(
        conn, message_id=mid, path="pathly/features/s-rt5/A.md", type="md", title="original"
    )
    row = dict(conn.execute("SELECT * FROM comms_artifacts WHERE id=?", (aid,)).fetchone())
    row["title"] = "would-be overwrite"

    insert_artifact_row(conn, row)  # id already exists -> INSERT OR IGNORE no-op

    current = conn.execute("SELECT title FROM comms_artifacts WHERE id=?", (aid,)).fetchone()
    assert current["title"] == "original"


# ── hydrate_board ─────────────────────────────────────────────────────────────────


def test_hydrate_board_skips_when_db_has_rows(tmp_path):
    conn = get_db()
    post_message(
        conn,
        board="feature",
        scope="s-skip",
        from_agent="human",
        type="nudge",
        text="already here",
    )
    snapshot = {
        "board": "feature",
        "scope": "s-skip",
        "version": 1,
        "messages": [
            {
                "id": "should-not-import",
                "board": "feature",
                "scope": "s-skip",
                "from_agent": "human",
                "to_agent": "*",
                "type": "nudge",
                "text": "from disk",
                "ts": "2026-01-01T00:00:00Z",
            }
        ],
        "artifacts": [],
    }
    path = tmp_path / "BOARD.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = hydrate_board(conn, "feature", "s-skip", path)

    assert result is False
    messages = get_all_messages(conn, "feature", "s-skip")
    assert len(messages) == 1
    assert messages[0]["text"] == "already here"


def test_hydrate_board_imports_into_empty_db(tmp_path):
    conn = get_db()
    snapshot = {
        "board": "feature",
        "scope": "s-hydrate",
        "version": 1,
        "messages": [
            {
                "id": "m1",
                "board": "feature",
                "scope": "s-hydrate",
                "from_agent": "human",
                "to_agent": "*",
                "type": "artifact",
                "text": "root message",
                "ts": "2026-01-01T00:00:00Z",
                "status": "pending",
            }
        ],
        "artifacts": [
            {
                "id": "a1",
                "message_id": "m1",
                "path": "pathly/features/s-hydrate/NOTES.md",
                "type": "md",
                "title": "Notes",
                "summary": "a summary",
                "created_at": "2026-01-01T00:00:00Z",
                "created_by": "human",
                "version": 1,
            }
        ],
    }
    path = tmp_path / "BOARD.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")

    result = hydrate_board(conn, "feature", "s-hydrate", path)

    assert result is True
    messages = get_all_messages(conn, "feature", "s-hydrate")
    assert len(messages) == 1
    assert messages[0]["id"] == "m1"
    assert messages[0]["text"] == "root message"

    artifacts = conn.execute(
        "SELECT * FROM comms_artifacts WHERE message_id=?", ("m1",)
    ).fetchall()
    assert len(artifacts) == 1
    assert artifacts[0]["path"] == "pathly/features/s-hydrate/NOTES.md"
    assert artifacts[0]["summary"] == "a summary"


def test_hydrate_board_missing_file_returns_false(tmp_path):
    conn = get_db()
    path = tmp_path / "does-not-exist" / "BOARD.json"
    assert hydrate_board(conn, "feature", "s-missing", path) is False
    assert get_all_messages(conn, "feature", "s-missing") == []


def test_hydrate_board_malformed_json_returns_false_without_raising(tmp_path):
    conn = get_db()
    path = tmp_path / "BOARD.json"
    path.write_text("{not valid json", encoding="utf-8")
    assert hydrate_board(conn, "feature", "s-bad", path) is False


# ── hydrate_project ───────────────────────────────────────────────────────────────


def test_hydrate_project_discovers_and_hydrates_project_and_feature_boards(tmp_path):
    conn = get_db()
    root_dir = tmp_path / "proj"
    norm_root = str(root_dir).replace("\\", "/").rstrip("/")

    project_snapshot = {
        "board": "project",
        "scope": norm_root,
        "version": 1,
        "messages": [
            {
                "id": "pm1",
                "board": "project",
                "scope": norm_root,
                "from_agent": "human",
                "to_agent": "*",
                "type": "nudge",
                "text": "project msg",
                "ts": "2026-01-01T00:00:00Z",
            }
        ],
        "artifacts": [],
    }
    feature_snapshot = {
        "board": "feature",
        "scope": "feat-h",
        "version": 1,
        "messages": [
            {
                "id": "fm1",
                "board": "feature",
                "scope": "feat-h",
                "from_agent": "human",
                "to_agent": "*",
                "type": "nudge",
                "text": "feature msg",
                "ts": "2026-01-01T00:00:00Z",
            }
        ],
        "artifacts": [],
    }

    project_path = root_dir / "pathly" / "project" / "BOARD.json"
    project_path.parent.mkdir(parents=True)
    project_path.write_text(json.dumps(project_snapshot), encoding="utf-8")

    feature_path = root_dir / "pathly" / "features" / "feat-h" / "BOARD.json"
    feature_path.parent.mkdir(parents=True)
    feature_path.write_text(json.dumps(feature_snapshot), encoding="utf-8")

    # A feature board that already has DB rows -> must be SKIPPED, never overwritten.
    post_message(
        conn,
        board="feature",
        scope="feat-already",
        from_agent="human",
        type="nudge",
        text="already here",
    )
    already_snapshot = {
        "board": "feature",
        "scope": "feat-already",
        "version": 1,
        "messages": [
            {
                "id": "should-not-import",
                "board": "feature",
                "scope": "feat-already",
                "from_agent": "human",
                "to_agent": "*",
                "type": "nudge",
                "text": "from disk",
                "ts": "2026-01-01T00:00:00Z",
            }
        ],
        "artifacts": [],
    }
    already_path = root_dir / "pathly" / "features" / "feat-already" / "BOARD.json"
    already_path.parent.mkdir(parents=True)
    already_path.write_text(json.dumps(already_snapshot), encoding="utf-8")

    result = hydrate_project(conn, str(root_dir))

    # "global" also lands in hydrated: db/migrations.py's startup backfill_board_mirrors
    # always writes an (empty) ~/.pathly/global/BOARD.json, so it exists independently
    # of this test's project_root and is legitimately picked up too.
    assert {norm_root, "feat-h"}.issubset(set(result["hydrated"]))
    assert "feat-already" not in result["hydrated"]
    assert result["skipped"] == ["feat-already"]

    project_messages = get_all_messages(conn, "project", norm_root)
    assert [m["id"] for m in project_messages] == ["pm1"]
    feature_messages = get_all_messages(conn, "feature", "feat-h")
    assert [m["id"] for m in feature_messages] == ["fm1"]
    already_messages = get_all_messages(conn, "feature", "feat-already")
    assert [m["text"] for m in already_messages] == ["already here"]


def test_hydrate_project_skips_nonexistent_project_and_feature_files(tmp_path):
    conn = get_db()
    root_dir = tmp_path / "empty-proj"
    root_dir.mkdir()

    result = hydrate_project(conn, str(root_dir))

    # No pathly/project or pathly/features/* on disk -> neither is attempted. "global"
    # is still processed (its BOARD.json always exists via the startup backfill), and
    # is empty (0 messages/artifacts) since nothing was posted to it in this test.
    assert result == {"hydrated": ["global"], "skipped": []}


def test_hydrate_project_handles_no_root_gracefully():
    conn = get_db()
    # No project_root -> only the always-present (empty) global mirror is processed;
    # it stays empty (0 rows) after each call, so a repeat call behaves identically.
    result = hydrate_project(conn, "")
    assert result == {"hydrated": ["global"], "skipped": []}
    result_none = hydrate_project(conn, None)
    assert result_none == {"hydrated": ["global"], "skipped": []}
