"""HQ acceptance: answers from real board facts, changes nothing (ticket 07).

Fixture board: 2 goals (one with 3/5 tasks done), 1 running run at a known
stage, 1 unanswered agent question. The question is posted the way agents
post them — option OBJECTS ({id, label, description}) under a goal — because
a plain-string fixture hid a crash on exactly that shape. The "model" is a
recording stub that echoes the packet's fact lines — no real model needed;
the assertions prove the grounding plumbing (the turn the model receives).

The DB is auto-isolated per test by tests/conftest.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

SCOPE = "hqaccept"
PR = "/tmp/hqaccept-proj"
RUN_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"  # bare uuid -> 'single' run
QUESTION = "Deploy to staging now?"
GOAL = "Goal: ship the thing"
STAGE = "BUILDING"
OPTIONS = [
    {"id": "a", "label": "Deploy now", "description": "ship to staging"},
    {"id": "b", "label": "Wait for review", "description": "hold"},
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _seed(conn):
    from pathly_orchestrator.db.queries.comms_messages import post_message
    from pathly_orchestrator.db.queries.run_history import upsert_run

    g1 = post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="planner",
        type="goal",
        text=GOAL,
        executor="single",
    )
    post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="planner",
        type="goal",
        text="Goal: polish docs",
        executor="single",
    )
    task_ids = [
        post_message(
            conn,
            board="feature",
            scope=SCOPE,
            from_agent="planner",
            type="task",
            text=f"Task {i + 1}",
            goal_id=g1,
        )
        for i in range(5)
    ]
    conn.executemany(
        "UPDATE comms_messages SET task_status='done' WHERE id=?",
        [(tid,) for tid in task_ids[:3]],
    )
    post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="builder",
        type="question",
        text=QUESTION,
        options=OPTIONS,
        goal_id=g1,
    )
    upsert_run(
        conn,
        PR,
        SCOPE,
        RUN_ID,
        "running",
        started_at=_now_iso(),
        finished_at=None,
        adapter="claude",
        board_scope=SCOPE,
    )
    conn.execute(
        "INSERT INTO agent_invocations "
        "(project_root, feature, run_id, stage, started_at, "
        "tokens_in, tokens_out, cost_usd, board_scope) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (PR, SCOPE, RUN_ID, STAGE, _now_iso(), 10, 5, 0.01, SCOPE),
    )
    conn.commit()


@pytest.fixture()
def board():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    _seed(conn)
    return conn


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _recording_stub(prompt: str, recordings: list) -> str:
    """Stands in for the local model: records the prompt, echoes the
    packet's fact lines back (what a grounded answer is built from)."""
    recordings.append(prompt)
    return "\n".join(ln for ln in prompt.splitlines() if ln.startswith("- "))


def _ask(client, message: str) -> dict:
    r = client.post(
        "/hq/prompt",
        json={
            "message": message,
            "board": SCOPE,
            "project_root": PR,
            "model": "qwen3-8b",
        },
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    return r.get_json()


def test_prompt_carries_board_facts(board, client):
    """The turn Studio sends the model (POST /hq/prompt) names the pending
    question with its options and goal, the run's stage, and goal progress."""
    from pathly_orchestrator.hq_prompt import HQ_SYSTEM_PROMPT

    turn = _ask(client, "what needs my attention?")
    assert turn["redirect"] is None
    assert turn["system_prompt"] == HQ_SYSTEM_PROMPT
    recordings: list = []
    answer = _recording_stub(turn["prompt"], recordings)
    assert QUESTION in answer
    assert "Deploy now, Wait for review" in answer
    assert f"[goal: {GOAL}]" in answer
    assert STAGE in answer
    assert "3/5 tasks done" in answer
    assert turn["prompt"].rstrip().endswith("what needs my attention?")
    assert len(recordings) == 1

    m = turn["manifest"]
    assert m["unavailable"] is False
    assert m["model"] == "qwen3-8b" and m["eligible_model"] is True
    included = {s["name"] for s in m["sections"] if s["included"]}
    assert {"questions", "runs", "goals"} <= included
    assert turn["context_tokens"] == 2 * m["budget"] + 4000


def _db_snapshot(conn) -> dict:
    """Every row of every table the HQ path could touch — an UPDATE in place
    changes this as surely as an INSERT does."""
    tables = (
        "comms_messages",
        "run_history",
        "fsm_events",
        "agent_invocations",
        "run_log",
        "app_settings",
    )
    return {
        t: [tuple(row) for row in conn.execute(f"SELECT * FROM {t} ORDER BY rowid")]
        for t in tables
    }


def test_hq_answer_path_writes_nothing(board, client):
    from pathly_orchestrator.hq_prompt import build_hq_prompt

    before = _db_snapshot(board)
    # The full HQ answer path: the turn Studio fetches, the one-string form,
    # the inspection endpoint, and the refusal path.
    _ask(client, "what needs my attention?")
    build_hq_prompt("what needs my attention?", SCOPE, PR)
    r = client.get(f"/hq/context?board={SCOPE}&project_root={PR}")
    assert r.status_code == 200
    _ask(client, "restart the builder")
    after = _db_snapshot(board)
    assert before == after


def test_action_redirect_zero_model_calls(board, client, monkeypatch):
    from pathly_orchestrator import hq_prompt

    calls: list = []

    def _counting(*a, **k):
        calls.append((a, k))
        raise AssertionError("an action request must not build a model turn")

    monkeypatch.setattr(hq_prompt, "build_hq_turn", _counting)
    turn = _ask(client, "restart the builder")
    assert turn["redirect"] == hq_prompt.HQ_READONLY_REDIRECT
    assert turn["system_prompt"] is None and turn["prompt"] is None
    assert turn["manifest"] is None
    assert calls == []
