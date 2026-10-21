"""role-read-policy 09: the server stamps author_role / author_run_id / author_source on every
board write, from the caller's run token and never from the request body.

Covers ``runner/provenance.py::stamp`` / ``system_stamp``, ``/comms/post`` end to end, the
server-internal writers (``system``), and two source scans that keep a new writer from being
forgotten: ``add_comms_provenance`` relabels every row left with a NULL ``author_source`` as
``legacy`` on each start, so a writer that skips the stamp would hide as ``legacy``.
"""

from __future__ import annotations

import ast
import json
import logging
import re

import pytest
from _paths import SRC

PKG = SRC / "pathly_orchestrator"

# The allowed values of comms_messages.author_source, pinned here independently of the code
# (a test below checks db/provenance_values.py defines the same set).
_SOURCES = frozenset({"token", "system", "legacy", "none"})


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting never spawns background threads during tests."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _mint(run_id="run-builder", role="builder"):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token

    return mint_run_token(
        get_db(), run_id, role, "feat-a", "/proj", "feature", "feat-a"
    )


def _row(message_id):
    from pathly_orchestrator.db.connection import get_db

    r = (
        get_db()
        .execute(
            "SELECT from_agent, run_id, type, author_role, author_run_id, author_source"
            " FROM comms_messages WHERE id=?",
            (message_id,),
        )
        .fetchone()
    )
    return dict(r)


def _provenance(row):
    return (row["author_role"], row["author_run_id"], row["author_source"])


def _post(client, token=None, **over):
    body = {
        "feature": "feat-a",
        "from": "explorer",
        "type": "discovery",
        "text": "found something",
        "board": "feature",
        "scope": "feat-a",
    }
    body.update(over)
    headers = {"X-Pathly-Run-Token": token} if token is not None else {}
    r = client.post("/comms/post", json=body, headers=headers)
    assert r.status_code == 200, r.data
    return r.get_json()["message_id"]


# ── stamp() / system_stamp() ───────────────────────────────────────────────────


def test_stamp_of_a_run_identity_is_the_run_role_and_id():
    from pathly_orchestrator.http_server.run_identity import CallerIdentity
    from pathly_orchestrator.runner.provenance import stamp

    ident = CallerIdentity(kind="run", run_id="r1", role="builder")
    assert stamp(ident) == {
        "author_role": "builder",
        "author_run_id": "r1",
        "author_source": "token",
    }


@pytest.mark.parametrize("kind", ["anonymous", "ui"])
def test_stamp_of_anything_but_a_run_is_none(kind):
    from pathly_orchestrator.http_server.run_identity import CallerIdentity
    from pathly_orchestrator.runner.provenance import stamp

    assert stamp(CallerIdentity(kind=kind)) == {
        "author_role": None,
        "author_run_id": None,
        "author_source": "none",
    }


@pytest.mark.parametrize("role", [None, "", "   "])
def test_stamp_of_a_run_identity_without_a_role_is_none_and_logs_the_run(role, caplog):
    """A live token whose run has no role cannot be attributed to a role, so the row is
    unverified: `token` is for a non-empty role only (a role-less row would pass every
    reviewer/tester wall, which only withholds `none` or a named role)."""
    from pathly_orchestrator.http_server.run_identity import CallerIdentity
    from pathly_orchestrator.runner.provenance import stamp

    ident = CallerIdentity(kind="run", run_id="run-norole", role=role)
    with caplog.at_level(logging.WARNING):
        got = stamp(ident)
    assert got == {"author_role": None, "author_run_id": None, "author_source": "none"}
    warned = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("run-norole" in r.getMessage() for r in warned), caplog.text


def test_system_stamp_is_system_and_takes_no_input():
    from pathly_orchestrator.runner.provenance import system_stamp

    assert system_stamp() == {
        "author_role": "system",
        "author_run_id": None,
        "author_source": "system",
    }


def test_provenance_module_does_not_import_the_http_layer():
    """caller_identity lives in http_server; stamp() takes the identity as a parameter."""
    tree = ast.parse((PKG / "runner" / "provenance.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported.add(
                (node.module or "") + "." + ",".join(a.name for a in node.names)
            )
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    assert not [i for i in imported if "http_server" in i or "flask" in i], imported


# ── POST /comms/post ───────────────────────────────────────────────────────────


def test_builder_token_with_explorer_from_is_stored_as_builder(client):
    token = _mint("run-builder", "builder")
    mid = _post(client, token=token, **{"from": "explorer"})
    row = _row(mid)
    assert _provenance(row) == ("builder", "run-builder", "token")
    assert (
        row["from_agent"] == "explorer"
    )  # still stored as written, never read by policy


def test_a_body_run_id_naming_another_run_changes_none_of_the_three(client):
    token = _mint("run-builder", "builder")
    mid = _post(client, token=token, run_id="run-reviewer")
    row = _row(mid)
    assert _provenance(row) == ("builder", "run-builder", "token")
    assert (
        row["run_id"] == "run-reviewer"
    )  # the old body column is still written as before


def test_a_post_with_no_token_is_source_none(client):
    mid = _post(client)
    assert _provenance(_row(mid)) == (None, None, "none")


def test_a_body_run_id_without_a_token_is_not_provenance(client):
    mid = _post(client, run_id="run-builder")
    assert _provenance(_row(mid)) == (None, None, "none")


def test_a_post_with_a_revoked_token_is_none_and_logged(client, caplog):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_tokens import revoke_run_tokens

    token = _mint("run-gone", "builder")
    revoke_run_tokens(get_db(), "run-gone")
    with caplog.at_level(logging.INFO):
        mid = _post(client, token=token)
    assert _provenance(_row(mid)) == (None, None, "none")
    assert any("run token" in r.getMessage() for r in caplog.records)


def test_a_post_with_an_unknown_token_is_none_not_refused(client):
    mid = _post(client, token="not-a-real-token")
    assert _provenance(_row(mid)) == (None, None, "none")


def test_a_role_less_token_post_is_none_and_the_reviewer_does_not_see_it(client):
    """The role-less run's discovery must not be a verified row with no role: under the
    built-in reviewer policy it is withheld (control: a verified explorer row is shown).
    """
    from pathly_orchestrator.runner.read_policy import BUILTIN_DEFAULTS, row_allowed

    reviewer = BUILTIN_DEFAULTS["reviewer"]
    norole = _row(_post(client, token=_mint("run-norole", None)))
    assert _provenance(norole) == (None, None, "none")
    assert row_allowed(norole, reviewer, None) is False

    explorer = _row(_post(client, token=_mint("run-explorer", "explorer")))
    assert _provenance(explorer) == ("explorer", "run-explorer", "token")
    assert row_allowed(explorer, reviewer, None) is True


# ── server-internal writers ────────────────────────────────────────────────────


def test_goal_verify_escalation_is_system():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.goal_verify import (
        post_gate_failure_escalation,
    )

    post_gate_failure_escalation(
        "feature",
        "feat-a",
        "goal-1",
        {"gate": "test", "reason": "x", "feedback_file": "y"},
    )
    row = (
        get_db()
        .execute(
            "SELECT author_role, author_run_id, author_source FROM comms_messages"
            " WHERE type='escalation' AND scope='feat-a'"
        )
        .fetchone()
    )
    assert tuple(row) == ("system", None, "system")


def test_task_retry_escalation_is_system():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.task_retry import _post_escalation

    _post_escalation("feature", "feat-a", "goal-1", "task-1", "do it", "boom", 3)
    row = (
        get_db()
        .execute(
            "SELECT author_role, author_run_id, author_source FROM comms_messages"
            " WHERE type='escalation' AND scope='feat-a'"
        )
        .fetchone()
    )
    assert tuple(row) == ("system", None, "system")


def test_scheduler_task_status_is_system():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor.scheduler import _post_task_status

    _post_task_status(get_db(), "feature", "feat-a", "Started: x")
    row = (
        get_db()
        .execute(
            "SELECT author_role, author_run_id, author_source FROM comms_messages"
            " WHERE type='status' AND scope='feat-a'"
        )
        .fetchone()
    )
    assert tuple(row) == ("system", None, "system")


def test_the_validate_at_write_nudge_in_comms_post_is_system(client, tmp_path):
    """The system nudge inside /comms/post is stamped system even though the request that
    caused it is an anonymous builder post."""
    from pathly_orchestrator.db.connection import get_db

    feat_dir = tmp_path / "pathly" / "features" / "feat-a"
    feat_dir.mkdir(parents=True)
    (feat_dir / "PROPOSAL.md").write_text("# Title\n\n## Real section\n\ntext\n")

    _post(
        client,
        type="task",
        **{"from": "planner"},
        project_root=str(tmp_path),
        context_refs=[{"artifact": "PROPOSAL.md", "anchor": "no-such-anchor"}],
    )
    rows = (
        get_db()
        .execute(
            "SELECT author_role, author_run_id, author_source FROM comms_messages"
            " WHERE type='nudge' AND from_agent='system'"
        )
        .fetchall()
    )
    assert [tuple(r) for r in rows] == [("system", None, "system")]


def test_the_sentinel_message_for_an_unattached_artifact_is_system(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_artifacts import (
        find_or_create_artifact_by_path,
    )

    f = tmp_path / "pathly" / "features" / "feat-a" / "NOTES.md"
    f.parent.mkdir(parents=True)
    f.write_text("# notes\n")
    art = find_or_create_artifact_by_path(get_db(), "feat-a", str(f))
    assert art is not None
    row = _row(art["message_id"])
    assert _provenance(row) == ("system", None, "system")


def test_ensure_attached_message_is_system():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_artifacts import ensure_attached

    art = ensure_attached(
        get_db(), "feat-a", "pathly/features/feat-a/DESIGN.md", role="designer"
    )
    assert _provenance(_row(art["message_id"])) == ("system", None, "system")


def test_post_system_stamps_system_and_cannot_be_overridden():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.provenance import post_system

    mid = post_system(
        get_db(),
        board="feature",
        scope="feat-a",
        from_agent="system",
        type="status",
        text="x",
    )
    assert _provenance(_row(mid)) == ("system", None, "system")
    with pytest.raises(TypeError):
        post_system(
            get_db(),
            board="feature",
            scope="feat-a",
            from_agent="system",
            author_source="token",
        )


def _system_status_rows():
    from pathly_orchestrator.db.connection import get_db

    rows = (
        get_db()
        .execute(
            "SELECT author_role, author_run_id, author_source FROM comms_messages"
            " WHERE type='status' AND from_agent='system'"
        )
        .fetchall()
    )
    return [tuple(r) for r in rows]


def _assert_all_system(rows, at_least=1):
    assert len(rows) >= at_least, rows
    assert all(r == ("system", None, "system") for r in rows), rows


def _fake_goal(scope="gs-prov"):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        get_db(),
        board="feature",
        scope=scope,
        from_agent="planner",
        type="goal",
        text="Goal: x",
        executor="single",
    )


def test_goals_stop_status_is_system(client):
    from pathly_orchestrator.supervisor import board_lock

    goal = _fake_goal("gs-stop")
    board_lock.acquire("feature", "gs-stop", "run-1")
    try:
        r = client.post("/comms/goals/stop", json={"goal_id": goal})
        assert r.status_code == 200 and r.get_json()["stopped"] is True
    finally:
        board_lock.release("feature", "gs-stop", "run-1")
    _assert_all_system(_system_status_rows())


def test_goals_run_status_is_system(client, monkeypatch):
    import pathly_orchestrator.supervisor.goal_run as _gr

    def _fake(goal_id, **kw):
        kw["on_start"]("run-1")
        return {"ok": True}

    monkeypatch.setattr(_gr, "start_goal_run", _fake)
    r = client.post("/comms/goals/run", json={"goal_id": _fake_goal()})
    assert r.status_code == 200, r.data
    _assert_all_system(_system_status_rows())


def test_goals_decompose_status_is_system(client, monkeypatch):
    import pathly_orchestrator.supervisor.goal_run as _gr

    def _fake(goal_id, **kw):
        kw["on_start"]("run-1")
        return {"ok": True}

    monkeypatch.setattr(_gr, "start_goal_decompose", _fake)
    r = client.post("/comms/goals/decompose", json={"goal_id": _fake_goal()})
    assert r.status_code == 200, r.data
    _assert_all_system(_system_status_rows())


def test_project_decompose_status_is_system(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    def _fake(board, scope, mode, **kw):
        kw["on_done"]("run-1", {})
        return {"ok": True, "run_id": "run-1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post(
        "/comms/project/decompose", json={"project": "projprov", "rigor": "light"}
    )
    assert r.status_code == 200, r.data
    _assert_all_system(_system_status_rows())


def test_project_consultation_status_is_system(client, monkeypatch):
    import pathly_orchestrator.supervisor.api as _api

    class _State:
        run_id = "run-1"

    monkeypatch.setattr(_api, "start_run", lambda **kw: _State())
    r = client.post(
        "/comms/project/decompose",
        json={"project": "projprov", "rigor": "consultation"},
    )
    assert r.status_code == 200, r.data
    _assert_all_system(_system_status_rows())


def test_consolidate_status_posts_are_system(client, monkeypatch):
    """Both the dedup summary line and the reflector lifecycle lines."""
    import pathly_orchestrator.db.queries.comms as _comms
    import pathly_orchestrator.supervisor.board_run as _br

    monkeypatch.setattr(_comms, "dedupe_board", lambda *a, **k: [("a", "b")])

    def _fake(board, scope, mode, **kw):
        kw["on_start"]("run-1")
        return {"ok": True, "run_id": "run-1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post("/comms/consolidate", json={"scope": "cons-prov", "mode": "full"})
    assert r.status_code == 200, r.data
    _assert_all_system(_system_status_rows(), at_least=2)


# ── handlers whose row content is the caller's keep the caller's role ───────────


def _rows_where(sql_where, params=()):
    from pathly_orchestrator.db.connection import get_db

    rows = (
        get_db()
        .execute(
            "SELECT from_agent, author_role, author_run_id, author_source"
            f" FROM comms_messages WHERE {sql_where}",
            params,
        )
        .fetchall()
    )
    return [tuple(r) for r in rows]


def test_code_query_log_row_keeps_the_callers_role(client):
    body = {"op": "symbol", "target": "x.py", "role": "explorer", "scope": "feat-a"}
    r = client.post("/code/query", json=body, headers={"X-Pathly-Run-Token": _mint()})
    assert r.status_code == 200, r.data
    assert _rows_where("from_agent='code-intel'") == [
        ("code-intel", "builder", "run-builder", "token")  # body role=explorer ignored
    ]


def test_code_query_log_row_of_an_anonymous_caller_is_none(client):
    body = {"op": "symbol", "target": "x.py", "role": "explorer", "scope": "feat-a"}
    assert client.post("/code/query", json=body).status_code == 200
    assert _rows_where("from_agent='code-intel'") == [
        ("code-intel", None, None, "none")
    ]


def _phase(client, tmp_path, token=None):
    (tmp_path / "pathly" / "features" / "feat-ph").mkdir(parents=True)
    r = client.post(
        "/record_phase",
        json={
            "feature": "feat-ph",
            "agent": "explorer",
            "phase": "implement",
            "event_type": "PHASE_START",
            "project_root": str(tmp_path).replace("\\", "/"),
        },
        headers={"X-Pathly-Run-Token": token} if token else {},
    )
    assert r.status_code == 200, r.data


def test_record_phase_row_keeps_the_callers_role(client, tmp_path):
    _phase(client, tmp_path, token=_mint())
    assert _rows_where("type='phase'") == [
        ("explorer", "builder", "run-builder", "token")  # body agent=explorer ignored
    ]


def test_record_phase_row_of_an_anonymous_caller_is_none(client, tmp_path):
    _phase(client, tmp_path)
    assert _rows_where("type='phase'") == [("explorer", None, None, "none")]


def test_context_pull_trail_keeps_the_callers_role(client, tmp_path):
    feat_dir = tmp_path / "pathly" / "features" / "feat-a"
    feat_dir.mkdir(parents=True)
    (feat_dir / "PROPOSAL.md").write_text("# Title\n\n## Real section\n\ntext\n")
    r = client.get(
        "/comms/artifacts/section",
        query_string={
            "scope": "feat-a",
            "artifact": "PROPOSAL.md",
            "anchor": "real-section",
            "project_root": str(tmp_path),
            "trail": "task-1",
        },
        headers={"X-Pathly-Run-Token": _mint()},
    )
    assert r.status_code == 200, r.data
    assert _rows_where("text LIKE '%context pull%'") == [
        ("agent", "builder", "run-builder", "token")
    ]


# ── promotion, hydration, validation ───────────────────────────────────────────


@pytest.mark.parametrize("who", ["token", "system"])
def test_a_promoted_copy_keeps_the_source_provenance_through_a_chain(client, who):
    """feature -> project -> global: SPEC C8 refuses a hop whose row is not token/system."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_promote import promote_message
    from pathly_orchestrator.runner.provenance import post_system

    if who == "token":
        mid = _post(client, token=_mint("run-dir", "director"), type="decision")
        want = ("director", "run-dir", "token")
    else:
        mid = post_system(
            get_db(),
            board="feature",
            scope="feat-a",
            from_agent="system",
            type="decision",
            text="d",
        )
        want = ("system", None, "system")
    assert _provenance(_row(mid)) == want

    conn = get_db()
    hop1 = promote_message(conn, mid, "project", "/proj", "director")
    assert hop1["status"] == "ok", hop1
    assert _provenance(_row(hop1["message_id"])) == want
    hop2 = promote_message(conn, hop1["message_id"], "global", "global", "director")
    assert hop2["status"] == "ok", hop2
    assert _provenance(_row(hop2["message_id"])) == want


def _snapshot_message(mid, **over):
    row = {
        "id": mid,
        "board": "feature",
        "scope": "feat-h",
        "from_agent": "builder",
        "to_agent": "*",
        "type": "discovery",
        "text": "found",
        "ts": "2026-01-01T00:00:00+00:00",
    }
    row.update(over)
    return row


def test_hydrating_a_pre_upgrade_snapshot_row_labels_it_legacy(tmp_path):
    """A BOARD.json exported before the upgrade has no author_* keys. Hydration must not
    leave them NULL: a NULL source is not `none`, so the reviewer wall would show the row
    until the next server start relabels it."""
    from pathly_orchestrator.board_mirror import hydrate_board
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.runner.read_policy import BUILTIN_DEFAULTS, row_allowed

    snap = {
        "messages": [
            _snapshot_message("old-1"),
            _snapshot_message(
                "new-1",
                author_role="explorer",
                author_run_id="run-x",
                author_source="token",
            ),
        ],
        "artifacts": [],
    }
    path = tmp_path / "BOARD.json"
    path.write_text(json.dumps(snap), encoding="utf-8")

    assert hydrate_board(get_db(), "feature", "feat-h", path) is True

    old, new = _row("old-1"), _row("new-1")
    assert _provenance(old) == ("builder", None, "legacy")
    assert _provenance(new) == ("explorer", "run-x", "token")  # already stamped: kept
    assert row_allowed(old, BUILTIN_DEFAULTS["reviewer"], None) is False


def test_post_message_rejects_an_unknown_author_source():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    for bad in ("admin", "", "Token"):
        with pytest.raises(ValueError, match="author_source"):
            post_message(
                get_db(),
                board="feature",
                scope="feat-a",
                from_agent="x",
                text="x",
                author_source=bad,
            )
    n = get_db().execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]
    assert n == 0


def test_the_provenance_values_are_defined_once_in_db():
    from pathly_orchestrator.db import provenance_values as pv
    from pathly_orchestrator.runner.provenance import stamp, system_stamp

    assert pv.AUTHOR_SOURCES == _SOURCES
    assert system_stamp() == dict(pv.SYSTEM_AUTHOR)
    assert system_stamp()["author_role"] == pv.SYSTEM_ROLE
    assert (
        system_stamp() is not system_stamp()
    )  # a fresh dict: callers may not mutate it
    from pathly_orchestrator.http_server.run_identity import CallerIdentity

    got = stamp(CallerIdentity(kind="run", run_id="r", role="builder"))
    assert got["author_source"] == pv.SOURCE_TOKEN


def test_post_message_stores_a_missing_source_as_none_not_null():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        get_db(),
        board="feature",
        scope="feat-a",
        from_agent="x",
        text="x",
        author_source=None,
    )
    assert _provenance(_row(mid)) == (None, None, "none")


def test_post_message_without_a_stamp_is_none_never_null():
    """A caller that forgets the stamp must land as `none`, not NULL: the startup backfill
    would relabel a NULL as `legacy` and the gap would not show."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        get_db(), board="feature", scope="feat-a", from_agent="builder", text="x"
    )
    assert _provenance(_row(mid)) == (None, None, "none")


def test_post_message_stores_the_three_values_it_is_given():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        get_db(),
        board="feature",
        scope="feat-a",
        from_agent="x",
        text="x",
        author_role="reviewer",
        author_run_id="r9",
        author_source="token",
    )
    assert _provenance(_row(mid)) == ("reviewer", "r9", "token")


def test_no_writer_leaves_author_source_null(client, tmp_path):
    """Drive a spread of insert paths and check none leaves author_source NULL."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import answer_question, post_message
    from pathly_orchestrator.db.queries.comms_artifacts import ensure_attached
    from pathly_orchestrator.http_server.blueprints.comms._helpers import (
        post_task_status,
    )
    from pathly_orchestrator.supervisor.scheduler import _post_task_status

    conn = get_db()
    task_id = _post(client, type="task", **{"from": "planner"})
    _post(client, token=_mint("r-a", "builder"))
    _post(client)
    q = post_message(conn, board="feature", scope="feat-a", from_agent="x", text="q?")
    answer_question(conn, q, "a")
    post_task_status(conn, task_id, "Started")
    _post_task_status(conn, "feature", "feat-a", "Started: x")
    ensure_attached(conn, "feat-a", "pathly/features/feat-a/PLAN.md", role="planner")

    n = conn.execute("SELECT COUNT(*) FROM comms_messages").fetchone()[0]
    assert n >= 8
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM comms_messages WHERE author_source IS NULL"
        ).fetchone()[0]
        == 0
    )


# ── instruction text that tells an agent to post ───────────────────────────────

_HEADER = "X-Pathly-Run-Token: $PATHLY_RUN_TOKEN"


def test_board_run_prompt_tells_the_agent_to_send_the_run_token():
    """Without the header a board-run agent's posts would be stamped `none`."""
    from pathly_orchestrator.supervisor import board_lock
    from pathly_orchestrator.supervisor.board_run import start_board_run

    calls: list = []

    def fake_spawn(**kwargs):
        calls.append(kwargs)
        return {"result": "ok"}

    board_lock._held.clear()
    start_board_run(
        "feature", "feat-token", "single-agent", spawn_fn=fake_spawn, block=True
    )
    prompt = calls[0]["prompt"]
    assert f"/comms/post with the header {_HEADER} and a JSON body" in prompt
    assert "artifact_type, and send the same header" in prompt


def test_catalog_channel_tells_the_agent_to_send_the_run_token_on_its_pulls():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_artifacts import ensure_attached
    from pathly_orchestrator.runner.comms_catalog import build_catalog_channel

    conn = get_db()
    ensure_attached(conn, "feat-cat", "pathly/features/feat-cat/SPEC.md", role="po")
    lines, count = build_catalog_channel(conn, "feature", "feat-cat")
    assert count == 1
    list_line = next(ln for ln in lines if ln.startswith("To list all:"))
    read_line = next(ln for ln in lines if ln.startswith("To read one:"))
    assert _HEADER in list_line
    assert "same header" in read_line


# ── source scans ───────────────────────────────────────────────────────────────
#
# The startup backfill relabels a NULL author_source as `legacy`, so a writer that skips
# the stamp would hide there. These scans keep a new writer from being forgotten. Each one
# works on a source string so the negative tests below can feed it the variant it must catch.

_RAW_NAMES = frozenset({"post_message", "_post_message"})
_AUTHOR_KEYS = ("author_role", "author_run_id", "author_source")


def _call_name(node):
    f = node.func
    return getattr(f, "id", None) or getattr(f, "attr", None)


def _is_stamp_expr(node):
    """The only `**` values a post_message call may carry: `stamp(caller_identity(request))`,
    `system_stamp()`, or the db-layer constant SYSTEM_AUTHOR (db/ cannot import runner).
    """
    if isinstance(node, ast.Name):
        return node.id == "SYSTEM_AUTHOR"
    if not isinstance(node, ast.Call) or node.keywords:
        return False
    name = _call_name(node)
    if name == "system_stamp":
        return not node.args
    if name == "stamp":
        return (
            len(node.args) == 1
            and isinstance(node.args[0], ast.Call)
            and _call_name(node.args[0]) == "caller_identity"
        )
    return False


def _passes_stamp(call):
    own = [kw for kw in call.keywords if (kw.arg or "").startswith("author_")]
    if any(not isinstance(kw.value, ast.Constant) for kw in own):
        return False  # a role/run/source taken from an expression (e.g. the body)
    for kw in call.keywords:
        if kw.arg is None and _is_stamp_expr(kw.value):
            return True
        if (
            kw.arg == "author_source"
            and isinstance(kw.value, ast.Constant)
            and kw.value.value in _SOURCES
        ):
            return True
    return False


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                yield node, alias


def _bound_names(tree):
    """local name -> the set of originals it is bound to by `from x import post_message|post_system [as y]`."""
    bound: dict[str, set[str]] = {}
    for _node, a in _imports(tree):
        if a.name in ("post_message", "post_system"):
            bound.setdefault(a.asname or a.name, set()).add(a.name)
    return bound


def _raw_names(tree):
    """Names that call the unstamped writer. A name bound ONLY to the system-stamping
    wrapper `post_system` (imported `as _post_message` in the size-frozen blueprints) is
    stamped by construction; a name bound to both is treated as raw."""
    bound = _bound_names(tree)
    wrapped_only = {n for n, o in bound.items() if o == {"post_system"}}
    return (
        _RAW_NAMES | {n for n, o in bound.items() if "post_message" in o}
    ) - wrapped_only


def _post_message_calls(source):
    tree = ast.parse(source)
    raw = _raw_names(tree)
    return [
        n for n in ast.walk(tree) if isinstance(n, ast.Call) and _call_name(n) in raw
    ]


def _unstamped(source):
    """Line numbers of post_message calls that do not carry a stamp."""
    return [c.lineno for c in _post_message_calls(source) if not _passes_stamp(c)]


def _bypasses(source):
    """Ways to reach post_message that a call scan by name cannot follow."""
    tree = ast.parse(source)
    raw = _raw_names(tree)
    out = []
    for node, a in _imports(tree):
        if a.name == "post_message" and a.asname not in (None, "_post_message"):
            out.append(f"line {node.lineno}: post_message imported as {a.asname}")
    call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            name = n.id
        elif isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load):
            name = n.attr
        else:
            continue
        if name in raw and id(n) not in call_funcs:
            out.append(f"line {n.lineno}: {name} used other than by calling it")
    for n in ast.walk(tree):
        if (
            isinstance(n, ast.Call)
            and _call_name(n) == "getattr"
            and any(isinstance(a, ast.Constant) and a.value in raw for a in n.args)
        ):
            out.append(f"line {n.lineno}: post_message looked up with getattr")
    return out


def _src_files(*subdirs):
    for root in [PKG / s for s in subdirs] or [PKG]:
        for path in sorted(root.rglob("*.py")):
            yield path.relative_to(PKG).as_posix(), path.read_text(encoding="utf-8")


def test_every_post_message_call_in_supervisor_and_runner_passes_a_stamp():
    seen = 0
    missing = []
    for rel, text in _src_files("supervisor", "runner"):
        seen += len(_post_message_calls(text))
        missing += [f"{rel}:{ln}" for ln in _unstamped(text)]
    assert seen >= 4, "the scan found almost no post_message calls; it is not looking"
    assert not missing, f"post_message without a stamp: {missing}"


# Files whose post_message calls rely on the `none` default instead of an explicit stamp.
# Each is listed with the reason; the test below fails if a file here stops needing the entry,
# so the list can only shrink.
_UNSTAMPED_ALLOW = {
    # answer_question: written for a caller that is a human in the UI (no run token until
    # RRP-2b), and its row is an `answer`, which no built-in policy withholds.
    "db/queries/comms_messages.py",
    # promote_message: the copy is not a new author; it carries the SOURCE row's three
    # author_* values (taken from the row, not from a stamp call), so a chain keeps them.
    "db/queries/comms_promote.py",
    # post_directive: forwards the stamp its caller computed (`**author`). db/ cannot import
    # runner/ to build one, and the scan accepts only a literal stamp expression. Its one caller
    # is POST /comms/directives, which passes `**stamp(caller_identity(request))`;
    # test_comms_directives_query.py scans every call of post_directive for that form.
    "db/queries/comms_directives.py",
}


def test_every_post_message_call_is_stamped_or_on_the_allow_list():
    unlisted = []
    for rel, text in _src_files():
        if rel not in _UNSTAMPED_ALLOW:
            unlisted += [f"{rel}:{ln}" for ln in _unstamped(text)]
    assert (
        not unlisted
    ), f"post_message without a stamp, not on the allow-list: {unlisted}"


def test_the_allow_list_has_no_stale_entries():
    stale = [
        rel
        for rel in _UNSTAMPED_ALLOW
        if not _unstamped((PKG / rel).read_text("utf-8"))
    ]
    assert not stale, f"no unstamped post_message call left in: {stale}"


def test_no_post_message_is_reached_by_an_alias_or_indirectly():
    found = []
    for rel, text in _src_files():
        found += [f"{rel} {b}" for b in _bypasses(text)]
    assert not found, found


def test_the_size_frozen_blueprints_post_through_the_system_wrapper():
    """goals.py, project.py and settings.py are over 400 lines, so they cannot grow by a
    stamp argument; their import lines bind `_post_message` to the stamping wrapper."""
    for name in ("goals", "project", "settings"):
        rel = f"http_server/blueprints/comms/{name}.py"
        tree = ast.parse((PKG / rel).read_text(encoding="utf-8"))
        bound = _bound_names(tree)
        assert bound.get("_post_message") == {"post_system"}, (rel, bound)
        assert _post_message_calls((PKG / rel).read_text("utf-8")) == [], rel


def _author_literals(source):
    """String literals given to an author_* keyword or dict key (None is the anonymous stamp)."""
    out = []
    for n in ast.walk(ast.parse(source)):
        if isinstance(n, ast.keyword) and n.arg in _AUTHOR_KEYS:
            val = n.value
            if isinstance(val, ast.Constant) and val.value is not None:
                out.append(val.lineno)
        elif isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if (
                    isinstance(k, ast.Constant)
                    and k.value in _AUTHOR_KEYS
                    and isinstance(v, ast.Constant)
                    and v.value is not None
                ):
                    out.append(v.lineno)
    return out


def test_no_author_value_is_hard_coded_outside_the_db_constants():
    found = []
    for rel, text in _src_files():
        found += [f"{rel}:{ln}" for ln in _author_literals(text)]
    assert (
        not found
    ), f"author_* literal; import it from db/provenance_values.py: {found}"


# ── INSERT scan ────────────────────────────────────────────────────────────────

# INSERT [OR x] INTO / REPLACE INTO, any case, the table bare, quoted ("" [] ``) or schema
# qualified, or a `{}` placeholder (an f-string table).
_INSERT = re.compile(
    r"(?:INSERT\s+(?:OR\s+\w+\s+)?|REPLACE\s+)INTO\s+"
    r'(?:["`\[]?\w+["`\]]?\s*\.\s*)?'
    r'["`\[]?(?:(?P<table>comms_messages)(?!\w)|(?P<dyn>\{\}))',
    re.IGNORECASE,
)

# Dynamic-table inserts that cannot name author_source in the statement. Each needs a reason.
_DYNAMIC_INSERT_ALLOW = {
    # Hydration copies a whole BOARD.json snapshot row, author_* columns included. A row from
    # an export made before the upgrade has none; hydrate_board then runs
    # add_comms_provenance, which labels it `legacy`. Rows exported after carry their own.
    "db/queries/comms_hydrate.py",
}


def _str_expr(node):
    """Text of a string-valued expression: a literal, an f-string (`{}` per field) or a `+`
    of those; None for anything else."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            p.value if isinstance(p, ast.Constant) else "{}" for p in node.values
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _str_expr(node.left), _str_expr(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _sql_strings(source):
    def walk(node):
        text = _str_expr(node)
        if text is not None:
            yield text
            return
        for child in ast.iter_child_nodes(node):
            yield from walk(child)

    yield from walk(ast.parse(source))


def _insert_findings(source):
    """(statements INSERTing into comms_messages without author_source, a dynamic-table INSERT seen)."""
    bad, dynamic = [], False
    for sql in _sql_strings(source):
        found = list(_INSERT.finditer(sql))
        for i, m in enumerate(found):
            if m.group("dyn"):
                dynamic = True
                continue
            end = found[i + 1].start() if i + 1 < len(found) else len(sql)
            if "author_source" not in sql[m.start() : end].lower():
                bad.append(sql[m.start() : m.start() + 60])
    return bad, dynamic


def test_every_insert_into_comms_messages_sets_author_source():
    bad = []
    dynamic_files = set()
    for rel, text in _src_files():
        statements, dynamic = _insert_findings(text)
        bad += [f"{rel}: {s}" for s in statements]
        if dynamic:
            dynamic_files.add(rel)
    assert not bad, f"INSERT INTO comms_messages without author_source: {bad}"
    assert dynamic_files <= _DYNAMIC_INSERT_ALLOW, (
        f"dynamic-table INSERT not on the allow-list: "
        f"{sorted(dynamic_files - _DYNAMIC_INSERT_ALLOW)}"
    )
    assert dynamic_files == _DYNAMIC_INSERT_ALLOW, "stale _DYNAMIC_INSERT_ALLOW entry"


def test_the_insert_scan_sees_the_real_inserts():
    """Guard against the scan going blind: post_message's and the sentinel's INSERTs exist."""
    found = set()
    for rel, text in _src_files():
        if any(
            (m := _INSERT.search(sql)) and m.group("table")
            for sql in _sql_strings(text)
        ):
            found.add(rel)
    assert found == {
        "db/queries/comms_messages.py",
        "db/queries/comms_artifacts.py",
    }


# ── negative tests: the scans catch what they used to miss ─────────────────────


@pytest.mark.parametrize(
    "sql",
    [
        "insert into comms_messages (id, text) values (?, ?)",  # lower case
        "Insert Or Ignore Into comms_messages (id) values (?)",  # mixed case
        "REPLACE INTO comms_messages (id, text) VALUES (?, ?)",
        "INSERT OR REPLACE INTO comms_messages (id) VALUES (?)",
        'INSERT INTO "comms_messages" (id) VALUES (?)',  # quoted
        "INSERT INTO [comms_messages] (id) VALUES (?)",
        "INSERT INTO `comms_messages` (id) VALUES (?)",
        "INSERT INTO main.comms_messages (id) VALUES (?)",  # qualified
        'INSERT INTO "main"."comms_messages" (id) VALUES (?)',
        "INSERT INTO comms_messages SELECT * FROM old_messages",  # no column list
    ],
)
def test_the_insert_scan_catches_the_variant(sql):
    assert _insert_findings(f"Q = {sql!r}\n") == ([sql[:60]], False)


def test_the_insert_scan_catches_a_split_string_literal():
    src = 'Q = "INSERT INTO " + "comms_messages (id) VALUES (?)"\n'
    assert _insert_findings(src)[0]


def test_the_insert_scan_catches_a_qualified_dynamic_table():
    assert _insert_findings('Q = f"INSERT INTO main.{t} (id) VALUES (?)"\n') == (
        [],
        True,
    )


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO comms_messages (id, author_source) VALUES (?, 'none')",
        "insert into comms_messages (id, author_source) values (?, 'none')",
        "INSERT INTO comms_messages_fts (rowid, text) VALUES (?, ?)",  # another table
        "INSERT INTO comms_artifacts (id) VALUES (?)",
    ],
)
def test_the_insert_scan_passes_a_sound_statement(sql):
    assert _insert_findings(f"Q = {sql!r}\n") == ([], False)


@pytest.mark.parametrize(
    "call",
    [
        'post_message(conn, board="b")',
        'post_message(conn, author_source=data["from"])',  # a body-derived value
        'post_message(conn, author_source="admin")',  # a literal outside the allowed set
        'post_message(conn, author_source="token", author_role=data["from"])',
        'post_message(conn, **stamp(CallerIdentity(role=data["from"])))',
        "post_message(conn, **stamp(identity))",  # not built from the request's token
        'post_message(conn, **{"author_source": "token"})',
        'post_message(conn, **dict(author_source="token"))',
        "post_message(conn, **stamp(caller_identity(request), extra=1))",
    ],
)
def test_the_call_scan_rejects_a_stamp_that_could_come_from_the_body(call):
    assert _unstamped(call + "\n") == [1]


@pytest.mark.parametrize(
    "call",
    [
        "post_message(conn, **stamp(caller_identity(request)))",
        "post_message(conn, **system_stamp())",
        "post_message(conn, **SYSTEM_AUTHOR)",
        'post_message(conn, author_source="system", author_role="system")',
    ],
)
def test_the_call_scan_accepts_a_server_side_stamp(call):
    assert _unstamped(call + "\n") == []


@pytest.mark.parametrize(
    "src",
    [
        "from m import post_message as pm\npm(conn)\n",
        "from m import post_message as _pm\n_pm(conn)\n",
        "import functools\nfrom m import post_message\nf = functools.partial(post_message, conn)\n",
        "from m import post_message\nwrite = post_message\n",
        "import m\nwrite = m.post_message\n",
        'import m\ngetattr(m, "post_message")(conn)\n',
        "from m import post_message\nrun(callback=post_message)\n",
    ],
)
def test_the_bypass_scan_catches_an_alias_or_an_indirect_use(src):
    assert _bypasses(src)


def test_the_bypass_scan_allows_the_recognised_forms():
    src = (
        "from m import post_message as _post_message\n"
        "from m import post_system as _post_system\n"
        "_post_message(conn, **system_stamp())\n"
        "m.post_message(conn, **system_stamp())\n"
    )
    assert _bypasses(src) == []


def test_a_name_bound_to_the_wrapper_is_stamped_but_not_one_bound_to_post_message():
    wrapped = "from r import post_system as _post_message\n_post_message(conn)\n"
    assert _unstamped(wrapped) == []
    raw = "from m import post_message as _post_message\n_post_message(conn)\n"
    assert _unstamped(raw) == [2]
    both = (
        "def a():\n    from r import post_system as _post_message\n"
        "def b():\n    from m import post_message as _post_message\n    _post_message(conn)\n"
    )
    assert _unstamped(both) == [5]


@pytest.mark.parametrize(
    "src",
    [
        'f(author_source="system")\n',
        'f(author_role="system")\n',
        'x = {"author_source": "token"}\n',
    ],
)
def test_the_literal_scan_catches_a_hard_coded_author_value(src):
    assert _author_literals(src)
