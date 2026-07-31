"""run_log store — per-spawn Complete Run Record (unified-control-plane P0, ARCHITECTURE §8.1).

Covers the three store fns (spawn INSERT + stdout UPDATE + get_run_log; missing-spawn-row
UPDATE is a no-op; full untruncated stdout round-trips) plus a lightweight check that the
P0(a) schema landed (table + index + nullable comms_messages.run_id; migration idempotent).
Isolation is handled by the _isolate_db autouse fixture in conftest.py.
"""

from __future__ import annotations

from pathlib import Path

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.run_log import (
    get_run_log,
    update_run_log_stdout,
    write_run_log_spawn,
)


def test_spawn_insert_stdout_update_and_get(tmp_path: Path) -> None:
    """A spawn INSERT then a stdout UPDATE round-trip through get_run_log on one row."""
    conn = get_db()
    write_run_log_spawn(
        conn,
        "run-A",
        stage="BUILDING",
        prompt_sent="the composed prompt",
        board_context_injected="board block",
        stdin=None,
    )
    rows = get_run_log(conn, "run-A")
    assert len(rows) == 1
    row = rows[0]
    assert row["run_id"] == "run-A"
    assert row["stage"] == "BUILDING"
    assert row["prompt_sent"] == "the composed prompt"
    assert row["board_context_injected"] == "board block"
    assert row["stdin"] is None
    assert row["stdout"] is None  # spawn-half only until the result callback fills it
    assert row["ts"]  # NOT NULL

    update_run_log_stdout(conn, "run-A", "PTY stdout tail")
    rows = get_run_log(conn, "run-A")
    assert len(rows) == 1  # UPDATE, not a second INSERT
    assert rows[0]["stdout"] == "PTY stdout tail"
    # the spawn-half fields survive the stdout UPDATE untouched
    assert rows[0]["prompt_sent"] == "the composed prompt"


def test_update_stdout_with_no_spawn_row_is_noop(tmp_path: Path) -> None:
    """update_run_log_stdout for an unknown run_id must not raise and must insert nothing."""
    conn = get_db()
    # no spawn row exists for this run_id
    update_run_log_stdout(conn, "run-missing", "orphan stdout")
    assert get_run_log(conn, "run-missing") == []


def test_update_targets_newest_row_for_run_id(tmp_path: Path) -> None:
    """When a run_id has multiple spawn rows, the stdout UPDATE fills only the newest."""
    conn = get_db()
    write_run_log_spawn(conn, "run-dup", stage="s1", prompt_sent="first")
    write_run_log_spawn(conn, "run-dup", stage="s2", prompt_sent="second")
    update_run_log_stdout(conn, "run-dup", "only-newest")
    rows = get_run_log(conn, "run-dup")  # ORDER BY id ASC
    assert len(rows) == 2
    assert rows[0]["stdout"] is None  # older row untouched
    assert rows[1]["stdout"] == "only-newest"  # newest row filled


def test_full_untruncated_stdout_roundtrips(tmp_path: Path) -> None:
    """The human answer (2026-07-24) is 'persist full stdout untruncated' — a large tail
    must store and read back byte-identical, with no truncation of our own."""
    conn = get_db()
    big = "x" * 200_000 + "\n<END-MARKER>"
    write_run_log_spawn(conn, "run-big", stage="BUILDING", prompt_sent="p")
    update_run_log_stdout(conn, "run-big", big)
    rows = get_run_log(conn, "run-big")
    assert len(rows) == 1
    assert rows[0]["stdout"] == big
    assert len(rows[0]["stdout"]) == len(big)
    assert rows[0]["stdout"].endswith("<END-MARKER>")


def test_p0a_schema_and_migration_idempotent(tmp_path: Path) -> None:
    """P0(a) acceptance: run_log table + its index exist, comms_messages.run_id is added
    nullable, and re-running the migration is a clean no-op."""
    from pathly_orchestrator.db.migrations import _run_migrations

    conn = get_db()  # first migration pass already ran inside get_db()

    tables = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "run_log" in tables

    idx = {r[1] for r in conn.execute("PRAGMA index_list(run_log)").fetchall()}
    assert "idx_run_log_run_id" in idx

    # comms_messages.run_id — present and nullable (notnull flag == 0)
    cm_cols = {
        r[1]: r for r in conn.execute("PRAGMA table_info(comms_messages)").fetchall()
    }
    assert "run_id" in cm_cols
    assert cm_cols["run_id"][3] == 0  # notnull == 0 → nullable

    # a pre-existing row survives the (idempotent) re-migration below
    write_run_log_spawn(conn, "run-persist", stage="s", prompt_sent="keep me")
    _run_migrations(conn)  # second pass — must be a clean no-op
    assert len(get_run_log(conn, "run-persist")) == 1
