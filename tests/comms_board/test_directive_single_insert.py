"""chief-agent 20, B6: a directive is written with one INSERT.

``post_directive`` used to call ``post_message``, which committed an ordinary pending ``decision``,
and then ran a second statement that set ``binding = 1``. If that second statement failed, the
ordinary row stayed (every role's prompt carried it as a normal decision) and a retry added a
second copy. The row is now written once with ``binding = 1`` in the INSERT: ``post_message`` takes
a keyword-only ``binding`` (default 0) that only ``post_directive`` passes, and ``/comms/post``
still ignores a ``binding`` in a body.
"""

from __future__ import annotations

import ast
import inspect
import re
import sqlite3

import pytest
from _paths import SRC
from directives_support import TEXT, _row, _rows
from mirror_drain_support import _mirrors_are_drained

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_directives import post_directive
from pathly_orchestrator.db.queries.comms_messages import post_message

WRITES_MESSAGES = re.compile(
    r"^\s*(INSERT|UPDATE|DELETE|REPLACE)\b[^;]*\bcomms_messages\b", re.I | re.S
)
UPDATES_MESSAGES = re.compile(r"^\s*UPDATE\s+comms_messages\b", re.I)
STAMP = dict(author_role="chief", author_run_id="chief-1", author_source="token")


def _run_traced(conn, call):
    statements: list[str] = []
    conn.set_trace_callback(statements.append)
    try:
        result = call()
    finally:
        conn.set_trace_callback(None)
    return result, statements


def test_a_directive_is_one_statement_that_writes_comms_messages_and_it_is_an_insert():
    conn = get_db()

    mid, statements = _run_traced(
        conn, lambda: post_directive(conn, "/proj", "builder", TEXT, **STAMP)
    )

    writes = [s for s in statements if WRITES_MESSAGES.match(s)]
    assert len(writes) == 1, statements
    assert writes[0].lstrip().upper().startswith("INSERT")
    assert "binding" in writes[0]
    assert not [s for s in statements if UPDATES_MESSAGES.match(s)], statements


def test_the_row_a_directive_stores_is_binding_a_decision_from_the_chief():
    conn = get_db()

    mid = post_directive(conn, "/proj", "builder", TEXT, **STAMP)

    row = _row(mid)
    assert (row["board"], row["scope"], row["type"], row["from_agent"]) == (
        "project",
        "/proj",
        "decision",
        "chief",
    )
    assert (row["to_agent"], row["text"], row["binding"]) == ("builder", TEXT, 1)
    assert row["status"] == "pending"
    assert (row["author_role"], row["author_run_id"], row["author_source"]) == (
        "chief",
        "chief-1",
        "token",
    )
    assert len(_rows()) == 1


def test_a_failing_update_of_comms_messages_cannot_leave_an_ordinary_decision_behind():
    conn = get_db()

    def deny_updates(action, table, column, database, trigger):
        denied = action == sqlite3.SQLITE_UPDATE and table == "comms_messages"
        return sqlite3.SQLITE_DENY if denied else sqlite3.SQLITE_OK

    conn.set_authorizer(deny_updates)
    try:
        mid = post_directive(conn, "/proj", "*", TEXT, **STAMP)
    finally:
        conn.set_authorizer(None)

    assert [row["id"] for row in _rows()] == [mid]
    assert _row(mid)["binding"] == 1


def test_a_failing_insert_stores_nothing_and_a_retry_stores_one_row():
    conn = get_db()

    def deny_inserts(action, table, column, database, trigger):
        denied = action == sqlite3.SQLITE_INSERT and table == "comms_messages"
        return sqlite3.SQLITE_DENY if denied else sqlite3.SQLITE_OK

    conn.set_authorizer(deny_inserts)
    try:
        with pytest.raises(sqlite3.DatabaseError):
            post_directive(conn, "/proj", "*", TEXT, **STAMP)
    finally:
        conn.set_authorizer(None)
    assert _rows() == []

    post_directive(conn, "/proj", "*", TEXT, **STAMP)

    assert len(_rows()) == 1


def test_post_message_takes_a_keyword_only_binding_that_defaults_to_0():
    parameter = inspect.signature(post_message).parameters["binding"]

    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default == 0


def test_post_message_stores_the_binding_it_is_given_and_0_by_default():
    conn = get_db()
    args = dict(board="project", scope="/proj", from_agent="chief", type="decision")

    plain = post_message(conn, text="plain", **args)
    flagged = post_message(conn, text="flagged", binding=1, **args)

    assert (_row(plain)["binding"], _row(flagged)["binding"]) == (0, 1)


def test_only_post_directive_passes_a_binding_to_post_message():
    callers = set()
    for path in sorted((SRC / "pathly_orchestrator").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "post_message" not in source:
            continue
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name == "post_message" and any(
                kw.arg == "binding" for kw in node.keywords
            ):
                callers.add(path.relative_to(SRC / "pathly_orchestrator").as_posix())

    assert callers == {"db/queries/comms_directives.py"}


def test_comms_post_still_ignores_a_binding_in_the_body():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    body = {
        "feature": "demo",
        "from": "builder",
        "type": "decision",
        "text": "an ordinary decision",
        "binding": 1,
    }
    with app.test_client() as client:
        answer = client.post("/comms/post", json=body)

    assert answer.status_code == 200, answer.get_data(as_text=True)
    row = _row(answer.get_json()["message_id"])
    assert (row["type"], row["binding"]) == ("decision", 0)
