"""chief-agent 12: what ``POST /comms/directives`` accepts in ``to_agent`` and ``text``.

``to_agent`` is ``*`` or a role name (``^[a-z][a-z0-9_-]{0,39}$``, so no upper case and no
padding: role matching is exact, and ``Builder`` would reach nobody). ``text`` is a non-empty
string of at most 8 KiB in UTF-8 bytes (the standing-orders block has no other cap, and one
oversized order would break every spawn's argv), with no control character but newline and tab
(a NUL makes ``subprocess`` raise for every spawn of the role until someone retires the order)
and no lone surrogate (it cannot be encoded). Each refusal is a 400 and stores nothing.
"""

from __future__ import annotations

import json

import pytest
from chief_human_support import (
    _no_watcher_outlives_its_test,
    chief_root,
    client,
    host,
    open_session,
    project,
)
from directives_support import (
    GONE,
    ROUTE,
    TEXT,
    TOKEN,
    _post,
    _recency_path,
    _row,
    _rows,
)


@pytest.mark.parametrize(
    "to_agent", ["*", "builder", "a", "a" * 40, "debug-fixer", "qa_2", "x9"]
)
def test_a_star_or_a_role_name_is_an_address(client, project, chief_root, to_agent):
    opened = open_session(project, chief_root)

    resp = _post(client, opened, to_agent=to_agent)

    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert _row(resp.get_json()["id"])["to_agent"] == to_agent


@pytest.mark.parametrize(
    "to_agent",
    [
        GONE,
        "",
        " ",
        "Builder",
        " builder",
        "builder ",
        "builder\n",
        "1builder",
        "-builder",
        "_builder",
        "a" * 41,
        "two words",
        "back/slash",
        "**",
        "*builder",
        "human?",
        "büilder",
        5,
        None,
        True,
        ["builder"],
    ],
    ids=repr,
)
def test_anything_else_is_not_an_address(client, project, chief_root, to_agent):
    opened = open_session(project, chief_root)

    resp = _post(client, opened, to_agent=to_agent)

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert "to_agent" in resp.get_json()["error"]
    assert _rows() == []


@pytest.mark.parametrize(
    "text",
    [
        "x",
        "a" * 8192,
        "é" * 4096,  # two bytes each: 8192 bytes in 4096 characters
        "one\ntwo\n\tthree",
        "line break   stays",
    ],
    ids=lambda t: f"{len(t)} chars, {len(t.encode())} bytes",
)
def test_a_text_up_to_8_kib_is_stored(client, project, chief_root, text):
    opened = open_session(project, chief_root)

    resp = _post(client, opened, text=text)

    assert resp.status_code == 201, resp.get_data(as_text=True)
    assert _row(resp.get_json()["id"])["text"] == text


def test_the_text_is_stored_without_its_padding(client, project, chief_root):
    opened = open_session(project, chief_root)

    resp = _post(client, opened, text=f"\n  {TEXT} \t\n")

    assert resp.status_code == 201
    assert _row(resp.get_json()["id"])["text"] == TEXT


@pytest.mark.parametrize(
    "text",
    [
        GONE,
        "",
        "   ",
        "\n\t",
        None,
        5,
        ["x"],
        {"a": 1},
        "a" * 8193,
        "é" * 4097,  # 4097 characters but 8194 bytes
        "a" * 8000 + "€" * 100,  # 8300 bytes
    ],
    ids=lambda t: "missing" if t is GONE else repr(t)[:30],
)
def test_a_text_that_is_empty_or_too_long_is_refused(client, project, chief_root, text):
    opened = open_session(project, chief_root)

    resp = _post(client, opened, text=text)

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert "text" in resp.get_json()["error"]
    assert _rows() == []


@pytest.mark.parametrize(
    "text",
    ["a\x00b", "\x00", "a\rb", "\x1b[2Jscreen", "a\x0bb", "a\x0cb", "a\x7fb", "a\x85b"],
    ids=lambda t: repr(t),
)
def test_a_control_character_is_refused(client, project, chief_root, text):
    """A NUL in a standing order would make every spawn of the role fail (``subprocess``
    refuses an argument with an embedded null byte) until someone retired it."""
    opened = open_session(project, chief_root)

    resp = _post(client, opened, text=text)

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert "control character" in resp.get_json()["error"]
    assert _rows() == []


def test_a_lone_surrogate_is_refused(client, project, chief_root):
    """JSON can carry ``\\ud800``, which no UTF-8 string can hold."""
    opened = open_session(project, chief_root)
    raw = json.dumps({"project_root": project, "to_agent": "*", "text": "a\ud800b"})
    assert "\\ud800" in raw

    resp = client.post(
        ROUTE,
        data=raw,
        content_type="application/json",
        headers={TOKEN: opened.run_token},
    )

    assert resp.status_code == 400, resp.get_data(as_text=True)
    assert "text" in resp.get_json()["error"]
    assert _rows() == []


@pytest.mark.parametrize("raw", [b"", b"[]", b"3", b"not json"])
def test_a_body_that_is_not_an_object_posts_nothing(client, project, chief_root, raw):
    opened = open_session(project, chief_root)

    resp = client.post(
        ROUTE,
        data=raw,
        content_type="application/json",
        headers={TOKEN: opened.run_token},
    )

    assert resp.status_code in (400, 403), resp.get_data(as_text=True)
    assert _rows() == []
