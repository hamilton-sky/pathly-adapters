"""chief-agent 12: ``post_directive`` and the edit refusal in the query layer."""

from __future__ import annotations

import pytest
from directives_support import TEXT, _row, _rows

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.comms_directives import get_binding_decisions


def test_post_directive_stores_a_binding_decision_of_the_chief():
    from pathly_orchestrator.db.queries.comms_directives import post_directive

    conn = get_db()

    mid = post_directive(
        conn,
        "/proj",
        "tester",
        TEXT,
        author_role="chief",
        author_run_id="chief-1",
        author_source="token",
    )

    row = _row(mid)
    assert (row["board"], row["scope"], row["type"], row["from_agent"]) == (
        "project",
        "/proj",
        "decision",
        "chief",
    )
    assert (row["to_agent"], row["text"], row["binding"]) == ("tester", TEXT, 1)
    assert row["status"] == "pending"
    assert (row["author_role"], row["author_run_id"], row["author_source"]) == (
        "chief",
        "chief-1",
        "token",
    )
    assert [
        r["id"] for r in get_binding_decisions(conn, ["project"], ["/proj"], "tester")
    ] == [mid]


def test_post_directive_with_an_unknown_author_source_stores_nothing():
    from pathly_orchestrator.db.queries.comms_directives import post_directive

    with pytest.raises(ValueError):
        post_directive(get_db(), "/proj", "*", TEXT, author_source="forged")

    assert _rows() == []


def test_update_message_text_answers_binding_and_leaves_the_row_alone():
    from pathly_orchestrator.db.queries.comms_directives import post_directive
    from pathly_orchestrator.db.queries.comms_edit import update_message_text

    conn = get_db()
    mid = post_directive(conn, "/proj", "*", TEXT, author_source="token")
    before = dict(_row(mid))

    assert update_message_text(conn, mid, "other words", author_source="token") == (
        "binding"
    )

    assert dict(_row(mid)) == before
