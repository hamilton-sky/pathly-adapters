"""chief-autopilot-round-two 11: an answer a chief relays is stamped ``chief_relayed``.

A chief answers a board question with ``POST /comms/answer`` and ``cite`` only; the gate checks
the cited ``chief_human_messages`` row and the route stores that message's own text. The answer
row stays ``from_agent: human`` (the words are the person's), and its author columns now say a
chief relayed them: ``author_role: chief``, ``author_run_id`` the chief's run (taken from its run
token, never from the body) and ``author_source: chief_relayed``. A tokenless answer is stored
``none`` as before; a mirror row that claims ``chief_relayed`` hydrates as ``legacy``.
"""

from __future__ import annotations

import secrets
import time
from pathlib import Path

import pytest
from binding_guard_support import _no_embedding_threads, message, row, write_board

from pathly_orchestrator.board_mirror import hydrate_board
from pathly_orchestrator.db.connection import get_db

TEXT = 'use CSV, it\'s what "ops" asked for\nand keep the header row'


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A project with the feature ``demo`` (a feature row is the project's when its folder is)."""
    root = tmp_path / "proj"
    (root / "pathly" / "features" / "demo").mkdir(parents=True)
    return root


def _chief(root: Path) -> tuple[str, dict]:
    """An operator chief session on ``root``, its style prompt recorded: (run id, headers)."""
    from pathly_orchestrator.db.queries import chief as sessions
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    conn = get_db()
    run_id = "chief-" + secrets.token_hex(6)
    sessions.create_session(
        conn,
        run_id=run_id,
        project_root=str(root),
        preset="operator",
        tier="operator",
        engine="claude",
        tab_id=run_id,
        cli_session_id=None,
        hook_secret_hash=None,
        settings_dir=None,
    )
    token = mint_run_token(conn, run_id, "chief", None, str(root), "project", str(root))
    _type(run_id, root, "You are the chief of this project.")
    return run_id, {"X-Pathly-Run-Token": token}


def _type(run_id: str, root: Path, text: str) -> int:
    """What the chief hook stores when the person submits ``text`` in the chief's tab."""
    from pathly_orchestrator.db.queries.chief import add_human_message

    return add_human_message(get_db(), run_id, str(root), text)["id"]


def _question() -> str:
    from pathly_orchestrator.db.queries.comms_messages import post_message

    return post_message(
        get_db(),
        board="feature",
        scope="demo",
        from_agent="builder",
        to_agent="*",
        type="question",
        text="A or B?",
    )


def _answer_row(question_id: str) -> dict:
    rows = get_db().execute(
        "SELECT from_agent, text, author_role, author_run_id, author_source"
        " FROM comms_messages WHERE reply_to = ? AND type = 'answer'",
        (question_id,),
    )
    found = [dict(r) for r in rows.fetchall()]
    assert len(found) == 1, found
    return found[0]


def test_a_chiefs_cited_answer_is_stored_chief_relayed(client, project):
    run_id, headers = _chief(project)
    question = _question()
    time.sleep(0.02)
    typed = _type(run_id, project, TEXT)

    resp = client.post(
        "/comms/answer",
        json={"question_id": question, "cite": typed},
        headers=headers,
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _answer_row(question) == {
        "from_agent": "human",
        "text": TEXT,
        "author_role": "chief",
        "author_run_id": run_id,
        "author_source": "chief_relayed",
    }


def test_a_tokenless_answer_is_stored_none(client, project):
    question = _question()

    resp = client.post(
        "/comms/answer", json={"question_id": question, "answer": "A, please"}
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert _answer_row(question) == {
        "from_agent": "human",
        "text": "A, please",
        "author_role": None,
        "author_run_id": None,
        "author_source": "none",
    }


def test_relayed_stamp_is_none_without_a_cited_chief_answer(project):
    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.http_server.chief_cite import relayed_stamp

    _run_id, headers = _chief(project)
    with app.test_request_context("/comms/answer", method="POST", headers=headers):
        assert relayed_stamp() is None  # a chief token, but the gate cited nothing
    with app.test_request_context("/comms/answer", method="POST"):
        from flask import g

        g.chief_cited_text = TEXT
        assert relayed_stamp() is None  # cited text, but no chief token


def test_chief_relayed_is_a_known_source_and_an_unknown_one_still_raises():
    from pathly_orchestrator.db import provenance_values as pv
    from pathly_orchestrator.db.queries.comms_messages import post_message

    assert pv.SOURCE_CHIEF_RELAYED == "chief_relayed"
    assert pv.SOURCE_CHIEF_RELAYED in pv.AUTHOR_SOURCES
    with pytest.raises(ValueError):
        post_message(
            get_db(),
            board="feature",
            scope="demo",
            from_agent="human",
            type="answer",
            text="x",
            author_source="chief-relayed",
        )


def test_a_mirror_row_claiming_chief_relayed_hydrates_as_legacy(tmp_path):
    claim = message(
        "m",
        "feature",
        "feat-r",
        author_role="chief",
        author_run_id="chief-1",
        author_source="chief_relayed",
    )
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-r", [claim])

    hydrate_board(get_db(), "feature", "feat-r", path)

    assert row("m")["author_source"] == "legacy"
