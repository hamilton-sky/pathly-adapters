"""A decompose's planner run must post each task with a check block or a `Check: none <why>` line.

`POST /comms/post` refuses (422, nothing stored) a `type: task` post whose caller holds a live
planner run token and whose text has neither. The role is read from the token, never the body:
a tokenless caller, a chief token and any other role post as before. The non-blocking
`ref_warning` for a task with no `context_refs` is unchanged.
"""

from __future__ import annotations

import pytest

CHECK_BLOCK = (
    "```check\n$ python -m pytest tests/test_widget.py -q\nexit 0\nprints passed\n```"
)


@pytest.fixture(autouse=True)
def _no_embed(monkeypatch):
    """Stub embed_async so posting never spawns background threads during tests."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _mint(run_id, role):
    """A live run token of ``role``; a chief token also gets its open session row."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries import chief as sessions
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    token = mint_run_token(
        get_db(), run_id, role, "feat-a", "/proj", "feature", "feat-a"
    )
    if role == "chief":
        sessions.create_session(
            get_db(),
            run_id=run_id,
            project_root="/proj",
            preset="operator",
            tier="operator",
            engine="claude",
            tab_id=None,
            cli_session_id=None,
            hook_secret_hash=None,
            settings_dir=None,
        )
    return token


def _task_count(marker):
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute(
            "SELECT COUNT(*) FROM comms_messages WHERE type='task' AND text LIKE ?",
            ("%" + marker + "%",),
        )
        .fetchone()
    )
    return row[0]


def _post(client, text, role=None, **extra):
    headers = {}
    if role is not None:
        headers["X-Pathly-Run-Token"] = _mint("run-" + role, role)
    body = {
        "feature": "feat-a",
        "from": "planner",
        "type": "task",
        "text": text,
        "project_root": "/proj",
        "context_refs": [{"artifact": "pathly/features/feat-a/DAG_PLAN.md"}],
    }
    body.update(extra)
    return client.post("/comms/post", json=body, headers=headers)


def test_planner_task_without_a_check_is_refused_and_not_stored(client):
    text = "T1 add the widget parser - marker-no-check\nFile: src/widget.py"
    r = _post(client, text, role="planner")
    assert r.status_code == 422
    body = r.get_json()
    assert body["error"] == 'task has no check block and no "Check: none <why>" line'
    assert body["reason"] == (
        "a decompose must post each task with its check block or a "
        "'Check: none <why>' line"
    )
    assert body["task"] == "T1 add the widget parser - marker-no-check"
    assert _task_count("marker-no-check") == 0


def test_refusal_task_field_is_the_first_line_cut_to_80_characters(client):
    first = "T9 " + "x" * 120
    r = _post(client, first + "\nmore text", role="planner")
    assert r.status_code == 422
    assert r.get_json()["task"] == first[:80]


def test_planner_task_with_a_check_block_is_posted(client):
    r = _post(client, "T2 marker-with-block\n\n" + CHECK_BLOCK, role="planner")
    assert r.status_code == 200, r.get_json()
    assert _task_count("marker-with-block") == 1


def test_planner_task_with_check_none_and_a_reason_is_posted(client):
    r = _post(client, "T3 marker-none-why\nCheck: none - docs only", role="planner")
    assert r.status_code == 200, r.get_json()
    assert _task_count("marker-none-why") == 1


@pytest.mark.parametrize("line", ["Check: none — docs only", "Check: none: docs only"])
def test_check_none_takes_a_dash_or_colon_before_the_reason(client, line):
    r = _post(client, "T3b marker-none-sep\n" + line, role="planner")
    assert r.status_code == 200, r.get_json()


@pytest.mark.parametrize("line", ["Check: none", "Check: none -", "Check: none —  "])
def test_planner_task_with_check_none_and_no_reason_is_refused(client, line):
    r = _post(client, "T4 marker-none-bare\n" + line, role="planner")
    assert r.status_code == 422
    assert _task_count("marker-none-bare") == 0


def test_an_empty_check_block_counts_as_no_check(client):
    r = _post(
        client, "T4b marker-empty-block\n```check\n# nothing\n```", role="planner"
    )
    assert r.status_code == 422
    assert _task_count("marker-empty-block") == 0


def test_a_check_block_that_does_not_parse_is_refused_with_the_parser_message(client):
    from pathly_orchestrator.proof.checks import ParseError, checks_in

    bad = "T5 marker-bad-block\n```check\nexit 0\n$ python -m pytest -q\n```"
    with pytest.raises(ParseError) as parsed:
        checks_in(bad)
    r = _post(client, bad, role="planner")
    assert r.status_code == 422
    assert r.get_json()["error"] == str(parsed.value)
    assert _task_count("marker-bad-block") == 0


@pytest.mark.parametrize("role", [None, "chief", "builder"])
def test_other_callers_post_a_checkless_task_as_before(client, role):
    marker = "marker-other-%s" % (role or "tokenless")
    sender = {"from": "chief"} if role == "chief" else {}
    r = _post(client, "T6 " + marker, role=role, **sender)
    assert r.status_code == 200, r.get_json()
    assert _task_count(marker) == 1


def test_a_planner_non_task_post_is_not_linted(client):
    r = client.post(
        "/comms/post",
        json={"feature": "feat-a", "from": "planner", "type": "status", "text": "hi"},
        headers={"X-Pathly-Run-Token": _mint("run-planner-status", "planner")},
    )
    assert r.status_code == 200, r.get_json()


def test_a_task_without_context_refs_still_gets_its_ref_warning(client):
    r = client.post(
        "/comms/post",
        json={
            "feature": "feat-a",
            "from": "planner",
            "type": "task",
            "text": "T7 marker-refless\nCheck: none - docs only",
        },
        headers={"X-Pathly-Run-Token": _mint("run-planner-refless", "planner")},
    )
    assert r.status_code == 200, r.get_json()
    assert r.get_json()["ref_warning"] == (
        "task has no context_refs; agents will fall back to unverified "
        "auto-derived context — add context_refs or pass no_refs=<reason>"
    )


def test_ref_warning_helper_matches_the_route():
    from pathly_orchestrator.http_server.blueprints.comms._task_post_lint import (
        ref_warning,
    )

    assert ref_warning({}, []) is not None
    assert ref_warning({"no_refs": "none apply"}, []) is None
    assert ref_warning({}, [{"artifact": "a.md"}]) is None
