import sqlite3
import pytest
from pathly_orchestrator.db.migrations import _run_migrations


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    _run_migrations(c)
    yield c
    c.close()


def test_slug_column_exists(conn):
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(comms_messages)")}
    assert "slug" in cols


def test_slug_unique_index_exists(conn):
    indexes = {row["name"] for row in conn.execute("PRAGMA index_list(comms_messages)")}
    assert "idx_comms_messages_slug" in indexes


def test_slug_unique_constraint_enforced(conn):
    # Two rows with same non-null slug must fail
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts) "
        "VALUES ('a1', 'feature', 'test', 'agent', 'progress', 'hello', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts, slug) "
        "VALUES ('a2', 'feature', 'test', 'agent', 'progress', 'world', '2026-01-01T00:00:00Z', 'same-slug')"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts, slug) "
            "VALUES ('a3', 'feature', 'test', 'agent', 'progress', 'dup', '2026-01-01T00:00:00Z', 'same-slug')"
        )
        conn.commit()


def test_two_null_slugs_both_succeed(conn):
    # Two rows with NULL slug must both succeed (partial index)
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts) "
        "VALUES ('b1', 'feature', 'test', 'agent', 'progress', 'first', '2026-01-01T00:00:00Z')"
    )
    conn.execute(
        "INSERT INTO comms_messages (id, board, scope, from_agent, type, text, ts) "
        "VALUES ('b2', 'feature', 'test', 'agent', 'progress', 'second', '2026-01-01T00:00:00Z')"
    )
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) FROM comms_messages WHERE id IN ('b1','b2')"
    ).fetchone()[0]
    assert count == 2


def test_migration_idempotent(conn):
    # Running _run_migrations a second time must not raise and column+index still present
    _run_migrations(conn)
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(comms_messages)")}
    assert "slug" in cols
    indexes = {row["name"] for row in conn.execute("PRAGMA index_list(comms_messages)")}
    assert "idx_comms_messages_slug" in indexes
