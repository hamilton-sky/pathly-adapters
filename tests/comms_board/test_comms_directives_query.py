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
# the identity the request was checked as, ``**stamp(identity)`` where ``identity`` is a name the
# enclosing function bound to ``caller_identity(...)`` (one lookup, used for the check and the
# stamp), and nothing built from the body. A second ``caller_identity`` call inside ``stamp(...)``
# is a second lookup: it can answer differently once the session has closed.

PKG = SRC / "pathly_orchestrator"


def _name(call) -> str | None:
    func = call.func
    return getattr(func, "id", None) or getattr(func, "attr", None)


def _bound_identities(function) -> frozenset[str]:
    """The names ``function`` assigns the result of a ``caller_identity(...)`` call."""
    names: set[str] = set()
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and _name(node.value) == "caller_identity"
        ):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return frozenset(names)


def _directive_calls(source: str) -> list[tuple[ast.Call, frozenset[str]]]:
    """Each call of ``post_directive`` with the identity names its enclosing functions bound."""
    found: list[tuple[ast.Call, frozenset[str]]] = []

    def visit(node: ast.AST, bound: frozenset[str]) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bound = bound | _bound_identities(node)
        if isinstance(node, ast.Call) and _name(node) == "post_directive":
            found.append((node, bound))
        for child in ast.iter_child_nodes(node):
            visit(child, bound)

    visit(ast.parse(source), frozenset())
    return found


def _has_the_request_stamp(call: ast.Call, bound: frozenset[str]) -> bool:
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
        and isinstance(stamp.args[0], ast.Name)
        and stamp.args[0].id in bound
    )


LOOKS_UP_ONCE = "def route(r):\n    identity = caller_identity(r)\n"


@pytest.mark.parametrize(
    "source",
    [
        "post_directive(conn, s, '*', t)",
        "post_directive(conn, s, '*', t, **data)",
        "post_directive(conn, s, '*', t, **stamp(identity))",
        "post_directive(conn, s, '*', t, **stamp(caller_identity(r)))",
        "post_directive(conn, s, '*', t, author_source='token')",
        "post_directive(conn, s, '*', t, **system_stamp())",
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t)",
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t, **data)",
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t, **stamp(other))",
        LOOKS_UP_ONCE
        + "    post_directive(conn, s, '*', t, **stamp(caller_identity(r)))",
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t, **stamp(identity.x))",
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t, **stamp(identity, 1))",
        LOOKS_UP_ONCE
        + "    post_directive(conn, s, '*', t, **stamp(identity), author_role='x')",
        LOOKS_UP_ONCE
        + "    post_directive(conn, s, '*', t, **stamp(identity), **more)",
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t, **system_stamp())",
        "def route(r, identity):\n    post_directive(conn, s, '*', t, **stamp(identity))",
        "def route(r):\n    identity = data.get('identity')\n"
        "    post_directive(conn, s, '*', t, **stamp(identity))",
        "def route(r):\n    identity = stamp_of(r)\n"
        "    post_directive(conn, s, '*', t, **stamp(identity))",
        "identity = caller_identity(r)\ndef route(r):\n"
        "    post_directive(conn, s, '*', t, **stamp(identity))",
        "def other(r):\n    identity = caller_identity(r)\ndef route(r):\n"
        "    post_directive(conn, s, '*', t, **stamp(identity))",
    ],
)
def test_the_scan_catches_a_call_without_the_request_stamp(source):
    ((found, bound),) = _directive_calls(source)

    assert not _has_the_request_stamp(found, bound)


@pytest.mark.parametrize(
    "source",
    [
        LOOKS_UP_ONCE + "    post_directive(conn, s, '*', t, **stamp(identity))",
        "async def route(r):\n    identity = caller_identity(request)\n"
        "    post_directive(conn, s, '*', t, **stamp(identity))",
        "def route(r):\n    identity = caller_identity(request)\n"
        "    def inner():\n        post_directive(conn, s, '*', t, **stamp(identity))",
    ],
)
def test_the_scan_accepts_the_request_stamp(source):
    ((found, bound),) = _directive_calls(source)

    assert _has_the_request_stamp(found, bound)


def test_every_call_of_post_directive_passes_the_request_stamp():
    calls = unstamped = 0
    for path in sorted(PKG.rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        if "post_directive" not in source:
            continue
        for call, bound in _directive_calls(source):
            calls += 1
            unstamped += not _has_the_request_stamp(call, bound)

    assert calls >= 1, "the scan found no call of post_directive; it is not looking"
    assert unstamped == 0
