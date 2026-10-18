"""POST /db/query runs its statement read-only.

The route checks the first word of the SQL, but `WITH x AS (SELECT 1) INSERT ...` starts with
an allowed word and used to write (a forged `run_tokens` row, a rewritten `author_*` stamp). The
statement now runs under `PRAGMA query_only = ON` on the request thread's connection, reset in a
`finally`. `execute` takes exactly one statement, so a caller cannot switch the pragma off from
inside its own SQL. The Flask test client serves the request on the test's own thread, so the
route and the test share one thread-local connection: a pragma left on would show up here.
"""

from __future__ import annotations

import pytest

_WITH_INSERT = (
    "WITH x AS (SELECT 1 AS n) "
    "INSERT INTO run_tokens (token_hash, run_id, role, created_at) "
    "SELECT 'forged-hash', 'forged-run', 'chief', 1.0 FROM x"
)
_WITH_UPDATE = (
    "WITH x AS (SELECT 1 AS n) "
    "UPDATE comms_messages SET author_role = 'chief', author_source = 'token' "
    "WHERE EXISTS (SELECT 1 FROM x)"
)
_WITH_DELETE = (
    "WITH x AS (SELECT 1 AS n) "
    "DELETE FROM comms_messages WHERE EXISTS (SELECT 1 FROM x)"
)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def conn():
    from pathly_orchestrator.db.connection import get_db

    return get_db()


@pytest.fixture()
def seeded(conn):
    """One board row with a builder stamp, so an UPDATE or DELETE has something to hit."""
    from pathly_orchestrator.db.queries.comms_messages import post_message

    post_message(
        conn,
        "feature",
        "ro-feature",
        "builder",
        type="status",
        text="seed row",
        author_role="builder",
        author_run_id="run-seed",
        author_source="token",
    )
    return conn


def _snapshot(conn) -> dict:
    return {
        "run_tokens": conn.execute("SELECT COUNT(*) FROM run_tokens").fetchone()[0],
        "messages": conn.execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0],
        "stamps": [
            tuple(r)
            for r in conn.execute(
                "SELECT id, author_role, author_source FROM comms_messages ORDER BY id"
            ).fetchall()
        ],
    }


def _query(client, sql: str):
    return client.post("/db/query", json={"sql": sql})


def _query_only(conn) -> int:
    return conn.execute("PRAGMA query_only").fetchone()[0]


@pytest.mark.parametrize(
    "sql",
    [_WITH_INSERT, _WITH_UPDATE, _WITH_DELETE],
    ids=["insert", "update", "delete"],
)
def test_write_behind_with_is_refused_and_changes_nothing(client, seeded, sql):
    before = _snapshot(seeded)
    assert before["messages"] >= 1

    resp = _query(client, sql)

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert "readonly" in resp.get_json()["error"].lower()
    assert _snapshot(seeded) == before


def test_second_statement_cannot_switch_the_pragma_off(client, seeded):
    before = _snapshot(seeded)

    resp = _query(client, "SELECT 1; PRAGMA query_only = OFF")
    assert resp.status_code == 400
    assert _snapshot(seeded) == before

    # A write sent after the attempt is still refused.
    resp = _query(client, _WITH_INSERT)
    assert resp.status_code == 400
    assert _snapshot(seeded) == before


def test_plain_select_still_returns_rows(client, seeded):
    resp = _query(client, "SELECT text FROM comms_messages WHERE text = 'seed row'")

    assert resp.status_code == 200
    assert resp.get_json()["rows"] == [{"text": "seed row"}]


def test_pragma_is_off_again_after_every_outcome(client, seeded):
    assert _query_only(seeded) == 0
    _query(client, "SELECT 1")
    assert _query_only(seeded) == 0
    _query(client, _WITH_INSERT)
    assert _query_only(seeded) == 0
    _query(client, "SELECT 1; PRAGMA query_only = OFF")
    assert _query_only(seeded) == 0
    _query(client, "SELECT * FROM no_such_table")
    assert _query_only(seeded) == 0


def test_normal_write_on_the_same_thread_works_after_a_refused_one(client, seeded):
    from pathly_orchestrator.db.queries.comms_messages import post_message

    assert _query(client, _WITH_INSERT).status_code == 400
    before = _snapshot(seeded)

    message_id = post_message(
        seeded,
        "feature",
        "ro-feature",
        "builder",
        type="status",
        text="written after a refused query",
        author_role="builder",
        author_run_id="run-after",
        author_source="token",
    )

    after = _snapshot(seeded)
    assert after["messages"] == before["messages"] + 1
    assert message_id in [row[0] for row in after["stamps"]]
