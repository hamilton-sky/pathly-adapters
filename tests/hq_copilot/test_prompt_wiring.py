"""Tests for hq_prompt.build_hq_prompt, GET /hq/context and POST /hq/prompt
(ticket 03; POST /hq/prompt is the turn Studio sends the model).

The DB is auto-isolated per test by tests/conftest.py.
"""

from __future__ import annotations

import pytest

SCOPE = "hqwiring"


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _seed(conn):
    from pathly_orchestrator.db.queries.comms import post_message

    gid = post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="planner",
        type="goal",
        text="Goal: wire it",
        executor="single",
    )
    post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="builder",
        type="question",
        text="Ship now?",
        options=["yes", "no"],
    )
    return gid


def test_build_hq_prompt_order():
    from pathly_orchestrator.db.connection import get_db

    _seed(get_db())
    from pathly_orchestrator.hq_prompt import build_hq_prompt, HQ_SYSTEM_PROMPT

    out = build_hq_prompt("what needs my attention?", SCOPE)
    i_prompt = out.index(HQ_SYSTEM_PROMPT)
    i_ctx_open = out.index("<pathly-context>")
    i_ctx_close = out.index("</pathly-context>")
    i_msg = out.index("what needs my attention?")
    assert i_prompt < i_ctx_open < i_ctx_close < i_msg
    assert "Ship now?" in out


def test_build_hq_prompt_marks_unavailable(monkeypatch):
    from pathly_orchestrator import hq_context
    from pathly_orchestrator.hq_prompt import build_hq_prompt, HQ_SYSTEM_PROMPT

    def _boom(*a, **k):
        raise hq_context.HQContextUnavailable("down")

    monkeypatch.setattr(hq_context, "assemble_packet", _boom)
    out = build_hq_prompt("hello?", SCOPE)
    assert "[board context unavailable]" in out
    assert HQ_SYSTEM_PROMPT in out
    assert "hello?" in out
    assert "<pathly-context>" not in out


def test_hq_context_endpoint_shape(client):
    from pathly_orchestrator.db.connection import get_db

    _seed(get_db())
    r = client.get(f"/hq/context?board={SCOPE}")
    assert r.status_code == 200
    data = r.get_json()
    assert "<pathly-context>" in data["packet"]
    assert "</pathly-context>" in data["packet"]
    assert isinstance(data["tokens_est"], int)
    assert data["budget"] == 6000
    sections = {s["name"]: s for s in data["sections"]}
    assert set(sections) == {
        "questions",
        "runs",
        "goals",
        "events",
        "artifacts",
        "summaries",
    }
    # Artifact summaries are opt-in: off unless the caller asks for them.
    assert sections["summaries"] == {
        "name": "summaries",
        "included": False,
        "cut_reason": "off",
        "tokens": 0,
    }
    assert sections["questions"]["included"] is True
    assert sections["goals"]["included"] is True
    for s in data["sections"]:
        assert "cut_reason" in s


def test_hq_context_unknown_board_404(client):
    r = client.get("/hq/context?board=no-such-board")
    assert r.status_code == 404


def test_hq_context_requires_board(client):
    r = client.get("/hq/context")
    assert r.status_code == 400


def test_hq_prompt_endpoint_turn(client):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.hq_prompt import HQ_SYSTEM_PROMPT

    _seed(get_db())
    r = client.post("/hq/prompt", json={"message": "what's stuck?", "board": SCOPE})
    assert r.status_code == 200
    data = r.get_json()
    assert data["redirect"] is None
    assert data["system_prompt"] == HQ_SYSTEM_PROMPT
    # The packet leads the user turn; the question sits closest to the answer.
    assert data["prompt"].index("<pathly-context>") < data["prompt"].index(
        "what's stuck?"
    )
    assert "Ship now?" in data["prompt"]
    assert data["manifest"]["unavailable"] is False
    assert data["manifest"]["board"] == SCOPE
    assert data["context_tokens"] == 2 * 6000 + 4000


def test_hq_prompt_requires_message_and_board(client):
    assert client.post("/hq/prompt", json={"board": SCOPE}).status_code == 400
    assert client.post("/hq/prompt", json={"message": "hi"}).status_code == 400
    assert client.post("/hq/prompt", data="not json").status_code == 400


def test_hq_prompt_empty_board_is_not_an_error(client):
    # A feature with nothing posted yet still gets a turn: the empty packet
    # lets the model say there is nothing on the board (spec edge case).
    r = client.post("/hq/prompt", json={"message": "status?", "board": "brand-new"})
    assert r.status_code == 200
    assert "board is empty" in r.get_json()["prompt"]


def test_hq_prompt_unavailable_context(client, monkeypatch):
    from pathly_orchestrator import hq_context

    def _boom(*a, **k):
        raise hq_context.HQContextUnavailable("down")

    monkeypatch.setattr(hq_context, "assemble_packet", _boom)
    data = client.post(
        "/hq/prompt", json={"message": "hello?", "board": SCOPE}
    ).get_json()
    assert data["prompt"].endswith("[board context unavailable]")
    assert data["manifest"]["unavailable"] is True
    assert data["manifest"]["sections"] == []


def test_hq_prompt_honors_budget_setting(client):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_setting

    conn = get_db()
    _seed(conn)
    set_setting(conn, "hq.context_budget_tokens", "3000")
    data = client.post("/hq/prompt", json={"message": "hi?", "board": SCOPE}).get_json()
    assert data["manifest"]["budget"] == 3000
    assert data["context_tokens"] == 2 * 3000 + 4000


def test_questions_render_option_objects_and_goal(client):
    """Agents post options as {id, label, description} objects; rendering
    them must not fail the packet (it used to raise and drop ALL context)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    gid = _seed(conn)
    post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="planner",
        type="question",
        text="Which store?",
        goal_id=gid,
        options=[{"id": "a", "label": "SQLite"}, {"id": "b"}, {"x": 1}],
    )
    prompt = client.post(
        "/hq/prompt", json={"message": "q?", "board": SCOPE}
    ).get_json()["prompt"]
    assert '"Which store?" (options: SQLite, b) [goal: Goal: wire it]' in prompt


def test_hq_prompt_sections_choice(client):
    """The checkboxes' choice reaches the packet; [] means no board context."""
    from pathly_orchestrator.db.connection import get_db

    _seed(get_db())
    body = {"message": "q?", "board": SCOPE, "sections": ["goals"]}
    data = client.post("/hq/prompt", json=body).get_json()
    included = {s["name"] for s in data["manifest"]["sections"] if s["included"]}
    assert included == {"goals"}
    assert "Ship now?" not in data["prompt"]

    body["sections"] = []
    data = client.post("/hq/prompt", json=body).get_json()
    assert "no board sections selected" in data["prompt"]

    r = client.get(f"/hq/context?board={SCOPE}&sections=questions")
    included = {s["name"] for s in r.get_json()["sections"] if s["included"]}
    assert included == {"questions"}
