"""role-read-policy: author_role / author_run_id / author_source on comms_messages, and the
one-time backfill that marks every row written before the upgrade as ``legacy``."""

from __future__ import annotations

import sqlite3

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.migrations_incremental import _add_additive_migrations
from pathly_orchestrator.db.migrations_provenance import add_comms_provenance

_PROVENANCE_COLUMNS = ("author_role", "author_run_id", "author_source")


def _add_message(conn, mid, from_agent, run_id=None, mtype="discovery") -> None:
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts, run_id)"
        " VALUES (?, 'feature', 'feat', ?, ?, 'body', '2026-01-01T00:00:00Z', ?)",
        (mid, from_agent, mtype, run_id),
    )
    conn.commit()


def _add_invocation(conn, run_id, agent_role) -> None:
    conn.execute(
        "INSERT INTO agent_invocations (project_root, feature, run_id, agent_role)"
        " VALUES ('C:/proj', 'feat', ?, ?)",
        (run_id, agent_role),
    )
    conn.commit()


def _provenance(conn, mid):
    row = conn.execute(
        "SELECT author_role, author_run_id, author_source FROM comms_messages WHERE id=?",
        (mid,),
    ).fetchone()
    return tuple(row)


def _all_provenance(conn):
    return [
        tuple(r)
        for r in conn.execute(
            "SELECT id, author_role, author_run_id, author_source"
            " FROM comms_messages ORDER BY id"
        ).fetchall()
    ]


def _seed_pre_upgrade_rows(conn) -> None:
    """Rows as the migration finds them: author_* all NULL."""
    _add_invocation(conn, "run-exp", "explorer")
    _add_invocation(conn, "run-spoof", "builder")
    _add_invocation(conn, "run-sup", "builder")
    _add_invocation(conn, "run-norole", None)
    _add_message(conn, "m-explorer", "explorer", "run-exp")
    _add_message(conn, "m-spoofed", "explorer", "run-spoof")
    _add_message(conn, "m-supervisor", "supervisor", mtype="status")
    _add_message(conn, "m-system", "system", "run-sup", mtype="status")
    _add_message(conn, "m-builder-no-inv", "builder")
    _add_message(conn, "m-builder-unknown-run", "builder", "run-gone")
    _add_message(conn, "m-builder-empty-role", "builder", "run-norole")
    _add_message(conn, "m-human", "human", mtype="decision")


def test_explorer_invocation_row_becomes_legacy_explorer() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    add_comms_provenance(conn)
    assert _provenance(conn, "m-explorer") == ("explorer", None, "legacy")


def test_role_comes_from_the_invocation_not_from_agent() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    add_comms_provenance(conn)
    assert _provenance(conn, "m-spoofed") == ("builder", None, "legacy")


def test_supervisor_and_system_become_legacy_system() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    add_comms_provenance(conn)
    assert _provenance(conn, "m-supervisor") == ("system", None, "legacy")
    # a server-internal author is system even when its run_id joins an invocation
    assert _provenance(conn, "m-system") == ("system", None, "legacy")


def test_builder_without_an_invocation_becomes_legacy_builder() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    add_comms_provenance(conn)
    assert _provenance(conn, "m-builder-no-inv") == ("builder", None, "legacy")
    assert _provenance(conn, "m-builder-unknown-run") == ("builder", None, "legacy")
    # an invocation that recorded no role is not a join: from_agent is kept
    assert _provenance(conn, "m-builder-empty-role") == ("builder", None, "legacy")
    assert _provenance(conn, "m-human") == ("human", None, "legacy")


def test_every_row_has_a_source_and_none_has_a_run() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    add_comms_provenance(conn)
    rows = _all_provenance(conn)
    assert len(rows) == 8
    assert all(source == "legacy" for _, _, _, source in rows)
    assert all(run is None for _, _, run, _ in rows)
    assert all(role for _, role, _, _ in rows)


def test_second_run_changes_no_row() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    add_comms_provenance(conn)
    before = _all_provenance(conn)
    changes = conn.total_changes
    add_comms_provenance(conn)
    assert _all_provenance(conn) == before
    assert conn.total_changes == changes


def test_a_row_stamped_after_the_upgrade_is_left_alone() -> None:
    conn = get_db()
    _add_invocation(conn, "run-tok", "explorer")
    _add_message(conn, "m-stamped", "supervisor", "run-tok")
    conn.execute(
        "UPDATE comms_messages SET author_role='builder', author_run_id='run-tok',"
        " author_source='token' WHERE id='m-stamped'"
    )
    conn.commit()
    add_comms_provenance(conn)
    assert _provenance(conn, "m-stamped") == ("builder", "run-tok", "token")


def test_additive_migrations_run_the_backfill() -> None:
    conn = get_db()
    _seed_pre_upgrade_rows(conn)
    _add_additive_migrations(conn)
    assert _provenance(conn, "m-explorer") == ("explorer", None, "legacy")
    assert all(source == "legacy" for _, _, _, source in _all_provenance(conn))


def test_columns_are_added_to_a_table_that_lacks_them() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        "CREATE TABLE comms_messages (id TEXT PRIMARY KEY, from_agent TEXT NOT NULL,"
        " run_id TEXT);"
        "CREATE TABLE agent_invocations (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " run_id TEXT, agent_role TEXT);"
        "INSERT INTO agent_invocations (run_id, agent_role) VALUES ('r1', 'explorer');"
        "INSERT INTO comms_messages VALUES ('a', 'explorer', 'r1');"
        "INSERT INTO comms_messages VALUES ('b', 'supervisor', NULL);"
        "INSERT INTO comms_messages VALUES ('c', 'builder', NULL);"
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(comms_messages)")}
    assert not cols & set(_PROVENANCE_COLUMNS)

    add_comms_provenance(conn)
    add_comms_provenance(conn)

    cols = {r["name"] for r in conn.execute("PRAGMA table_info(comms_messages)")}
    assert set(_PROVENANCE_COLUMNS) <= cols
    assert _provenance(conn, "a") == ("explorer", None, "legacy")
    assert _provenance(conn, "b") == ("system", None, "legacy")
    assert _provenance(conn, "c") == ("builder", None, "legacy")
