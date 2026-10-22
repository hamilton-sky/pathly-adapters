"""chief-agent 20, B2: a lone surrogate in a comms body is a 400, not a 500.

Python's JSON parser accepts ``"\\ud800"``, SQLite cannot store it, and the route then failed with
``UnicodeEncodeError`` and answered 500 with the error text. ``read_json_body`` now treats a body
that holds a lone surrogate, in a key or in a string at any depth, like any other body it cannot
read: it returns its default, so each route answers what it already answers an unreadable body
(a 400) and nothing is stored. Other non-ASCII text, a surrogate pair and a cp1252 body read as
before. All eight routes are tried for a caller with no token; an operator chief reaches the reader
only through ``/comms/post`` (the gate turns it back on the others), so it is tried there.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from chief_gate_support import _chief, _gated, app, project
from mirror_drain_support import _mirrors_are_drained

LONE = "\ud800"
MESSAGE = {"feature": "demo", "from": "chief", "type": "discovery", "text": "hello"}


def _fields(mark: str, seed: str) -> dict[str, tuple[str, dict]]:
    """Per route, the body that names ``mark`` in the one field that route stores or looks up.
    ``seed`` is the id of a message that exists, so a route that checks the other id first (the
    old id of a supersede, the id of an edit) goes on to the one with the mark."""
    return {
        "post-text": ("/comms/post", {**MESSAGE, "text": f"a{mark}b"}),
        "post-scope": (
            "/comms/post",
            {**MESSAGE, "board": "project", "scope": f"/x{mark}"},
        ),
        "post-feature": ("/comms/post", {**MESSAGE, "feature": f"demo{mark}"}),
        "acknowledge": (
            "/comms/acknowledge",
            {"message_id": f"m{mark}", "agent": "builder"},
        ),
        "supersede": ("/comms/supersede", {"old_id": seed, "new_id": f"n{mark}"}),
        "edit": ("/comms/edit", {"message_id": seed, "text": f"t{mark}"}),
        "goals-run": ("/comms/goals/run", {"goal_id": f"g{mark}"}),
        "delete": ("/comms/delete", {"message_id": f"m{mark}"}),
    }


FIELD_NAMES = list(_fields("x", "seed"))


@pytest.fixture()
def demo(project: Path) -> Path:
    (project / "pathly" / "features" / "demo").mkdir(parents=True)
    return project


@pytest.fixture()
def seed(demo: Path) -> str:
    """The id of a message that exists, on the feature board the bodies name."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        get_db(),
        board="feature",
        scope="demo",
        from_agent="builder",
        type="discovery",
        text="a message that exists",
    )


@pytest.fixture()
def client(app, monkeypatch):
    """Under ``TESTING`` Flask raises an unhandled error instead of answering 500."""
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    with app.test_client() as c:
        yield c


def _rows() -> int:
    from pathly_orchestrator.db.connection import get_db

    return get_db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]


def _send(client, route: str, body, headers: dict, root: Path, encoding="utf-8"):
    """``body`` as JSON text (``json.dumps`` writes a lone surrogate as ``\\ud800``); a body
    that names a project root gets the chief's own."""
    if isinstance(body, dict) and route == "/comms/goals/run":
        body = {**body, "project_root": str(root)}
    data = body if isinstance(body, bytes) else json.dumps(body).encode(encoding)
    return client.post(
        route, data=data, content_type="application/json", headers=headers
    )


# The gate answers 403 to a chief for the other six before the route reads anything (a surrogate
# is not an id of its project, ``/comms/edit`` and ``/comms/delete`` are not routes a chief may
# call), so a chief reaches the reader only through these two fields of ``/comms/post``.
THROUGH_THE_GATE = ["post-text", "post-feature"]
CASES = [(field, "no-token") for field in FIELD_NAMES] + [
    (field, "chief") for field in THROUGH_THE_GATE
]


def _headers(who: str, root: Path) -> dict:
    return {} if who == "no-token" else _chief("operator", root).headers


@pytest.mark.parametrize(
    "field, who", CASES, ids=[f"{field}-{who}" for field, who in CASES]
)
def test_a_lone_surrogate_gets_the_400_an_unreadable_body_gets_and_nothing_is_stored(
    app, client, demo, seed, field, who
):
    route, body = _fields(LONE, seed)[field]
    headers = _headers(who, demo)
    before = _rows()

    # The same body without the surrogate, in UTF-16: ``get_json`` (which the gate also reads)
    # understands it and ``read_json_body`` does not, so the gate lets it through and the route
    # answers what it answers a body it cannot read.
    plain = _fields("x", seed)[field][1]
    unreadable = _send(client, route, plain, headers, demo, "utf-16")
    answer = _send(client, route, body, headers, demo)

    assert not _gated(unreadable), unreadable.get_json()
    assert unreadable.status_code == 400, unreadable.get_data(as_text=True)
    assert not _gated(answer), answer.get_json()
    assert answer.status_code == 400, answer.get_data(as_text=True)
    assert answer.get_json() == unreadable.get_json()
    assert _rows() == before


@pytest.mark.parametrize("field", [f for f in FIELD_NAMES if f not in THROUGH_THE_GATE])
def test_the_gate_still_turns_a_chief_back_before_the_route_where_it_did_before(
    app, client, demo, seed, field
):
    """A control, green before this change too: the six routes a chief cannot reach."""
    route, body = _fields(LONE, seed)[field]
    before = _rows()

    answer = _send(client, route, body, _headers("chief", demo), demo)

    assert _gated(answer), answer.get_data(as_text=True)
    assert _rows() == before


@pytest.mark.parametrize(
    "body",
    [
        {**MESSAGE, f"k{LONE}": 1},
        {**MESSAGE, "options": [{"deep": [[f"x{LONE}"]]}]},
        {**MESSAGE, "unread": {"a": {"b": [{"c": LONE}]}}},
    ],
    ids=["in-a-key", "nested-in-a-list", "under-a-key-the-route-ignores"],
)
def test_a_surrogate_in_a_key_or_deep_in_the_body_is_refused_too(client, demo, body):
    before = _rows()

    answer = _send(client, "/comms/post", body, {}, demo)

    assert answer.status_code == 400, answer.get_data(as_text=True)
    assert _rows() == before


def _read(app, data: bytes, default=None):
    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        read_json_body,
    )

    with app.test_request_context(
        "/comms/post", method="POST", data=data, content_type="application/json"
    ):
        return read_json_body(default)


def test_the_reader_returns_its_default_for_a_body_with_a_lone_surrogate(app):
    for escape in (
        b'"a\\ud800b"',
        b'"\\udfff"',
        b'"\\ud800\\ud800"',
        b'"\\ude00\\ud83d"',
    ):
        raw = b'{"text": ' + escape + b"}"
        assert _read(app, raw) is None
        assert _read(app, raw, {}) == {}
        assert _read(app, raw, {"fallback": 1}) == {"fallback": 1}


def test_the_reader_finds_a_surrogate_in_a_body_nested_deeper_than_it_is_wide(app):
    deep = b"[" * 300 + b'"\\ud800"' + b"]" * 300
    raw = b'{"a": ' + deep + b"}"

    assert _read(app, raw, {}) == {}


def test_the_reader_still_reads_other_text(app):
    text = "café ✓ 日本語 \U0001f600 —"
    pair = b'{"text": "\\ud83d\\ude00 pair"}'

    assert _read(app, json.dumps({"text": text}).encode("utf-8")) == {"text": text}
    assert _read(
        app, json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    ) == {"text": text}
    assert _read(app, pair) == {"text": "\U0001f600 pair"}


def test_the_reader_still_reads_a_cp1252_body_and_refuses_a_surrogate_in_one(app):
    body = '{"text": "one — dash"}'.encode("cp1252")
    with_lone = '{"text": "one — dash \\ud800"}'.encode("cp1252")

    assert body.count(b"\x97") == 1
    assert _read(app, body) == {"text": "one — dash"}
    assert _read(app, with_lone) is None


def test_a_message_with_other_text_is_still_stored_by_the_route(client, demo):
    body = {**MESSAGE, "text": "café \U0001f600 —"}
    before = _rows()

    answer = _send(client, "/comms/post", body, {}, demo)

    assert answer.status_code == 200, answer.get_data(as_text=True)
    assert _rows() == before + 1
