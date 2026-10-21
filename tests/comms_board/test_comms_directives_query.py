"""chief-agent 12: ``post_directive``, the edit refusal and who stamps a directive (query layer)."""

from __future__ import annotations

import ast

import pytest
from _paths import SRC
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


# --- who stamps a directive -----------------------------------------------------------
#
# ``post_directive`` forwards ``**author``, which the source scan of ``test_comms_provenance``
# cannot follow, so ``db/queries/comms_directives.py`` is on its allow-list. This scan closes the
# gap from the other side: every call of ``post_directive`` must pass the server-side stamp of
# the request, ``**stamp(caller_identity(request))``, and nothing built from the body.

PKG = SRC / "pathly_orchestrator"


def _name(call) -> str | None:
    func = call.func
    return getattr(func, "id", None) or getattr(func, "attr", None)


def _directive_calls(source: str) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.Call) and _name(n) == "post_directive"
    ]


def _has_the_request_stamp(call: ast.Call) -> bool:
    splats = [kw.value for kw in call.keywords if kw.arg is None]
    own = [kw for kw in call.keywords if (kw.arg or "").startswith("author_")]
    if len(splats) != 1 or own:
        return False
    stamp = splats[0]
    return (
        isinstance(stamp, ast.Call)
        and _name(stamp) == "stamp"
        and not stamp.keywords
        and len(stamp.args) == 1
        and isinstance(stamp.args[0], ast.Call)
        and _name(stamp.args[0]) == "caller_identity"
    )


@pytest.mark.parametrize(
    "call",
    [
        "post_directive(conn, s, '*', t)",
        "post_directive(conn, s, '*', t, **data)",
        "post_directive(conn, s, '*', t, **stamp(identity))",
        "post_directive(conn, s, '*', t, **stamp(caller_identity(r)), author_role='x')",
        "post_directive(conn, s, '*', t, author_source='token')",
        "post_directive(conn, s, '*', t, **system_stamp())",
    ],
)
def test_the_scan_catches_a_call_without_the_request_stamp(call):
    (found,) = _directive_calls(call)

    assert not _has_the_request_stamp(found)


def test_the_scan_accepts_the_request_stamp():
    (found,) = _directive_calls(
        "post_directive(conn, s, '*', t, **stamp(caller_identity(request)))"
    )

    assert _has_the_request_stamp(found)


def test_every_call_of_post_directive_passes_the_request_stamp():
    calls = unstamped = 0
    for path in sorted(PKG.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "post_directive" not in source:
            continue
        for call in _directive_calls(source):
            calls += 1
            unstamped += not _has_the_request_stamp(call)

    assert calls >= 1, "the scan found no call of post_directive; it is not looking"
    assert unstamped == 0
