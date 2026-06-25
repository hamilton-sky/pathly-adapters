"""unified-ai-routing Conv 6 — /record_phase mirrors phase boundaries onto the board.

POST /record_phase appends to the event log AND posts a `phase`-type comms message to
the feature board (best-effort), so the Command Center shows live progress in both
interactive (team-http) and headless (supervisor) runs. The `phase` type is excluded
from retrieve_board_context so it never bloats headless CLI-engine prompts.
"""

from __future__ import annotations

import uuid

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _phase_messages(scope):
    from pathly_orchestrator.db.connection import get_db

    rows = (
        get_db()
        .execute(
            "SELECT text, stage, from_agent, board FROM comms_messages "
            "WHERE scope=? AND type='phase'",
            (scope,),
        )
        .fetchall()
    )
    return [dict(r) for r in rows]


def test_record_phase_posts_phase_message_to_board(client, tmp_path):
    feature = f"phasebd-{uuid.uuid4().hex[:8]}"
    # record_phase requires the feature dir to exist.
    (tmp_path / "pathly" / "plans" / feature).mkdir(parents=True)

    r = client.post(
        "/record_phase",
        json={
            "feature": feature,
            "agent": "builder",
            "phase": "implement",
            "event_type": "PHASE_START",
            "project_root": str(tmp_path).replace("\\", "/"),
        },
    )
    assert r.status_code == 200, r.data

    msgs = _phase_messages(feature)
    assert len(msgs) == 1, msgs
    assert msgs[0]["board"] == "feature"
    assert msgs[0]["stage"] == "implement"
    assert msgs[0]["from_agent"] == "builder"
    assert "implement" in msgs[0]["text"] and "started" in msgs[0]["text"]


def test_phase_done_also_posts(client, tmp_path):
    feature = f"phasebd-{uuid.uuid4().hex[:8]}"
    (tmp_path / "pathly" / "plans" / feature).mkdir(parents=True)
    root = str(tmp_path).replace("\\", "/")

    for evt in ("PHASE_START", "PHASE_DONE"):
        r = client.post(
            "/record_phase",
            json={
                "feature": feature,
                "agent": "reviewer",
                "phase": "review",
                "event_type": evt,
                "project_root": root,
            },
        )
        assert r.status_code == 200, r.data

    texts = sorted(m["text"] for m in _phase_messages(feature))
    assert texts == ["review done", "review started"]


def test_phase_excluded_from_board_context():
    """`phase` is in the type-exclusion the board-context filter applies, so phase
    markers never reach injected agent prompts (the headless-prompt guard)."""
    import inspect

    import pathly_orchestrator.runner.comms_context as cc

    # _is_context is a private closure; assert the exclusion is present in source so
    # a future refactor that drops it trips this regression guard.
    src = inspect.getsource(cc)
    assert '== "phase"' in src and "return False" in src
