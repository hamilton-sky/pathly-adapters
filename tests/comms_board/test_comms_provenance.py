"""role-read-policy 09: the server stamps author_role / author_run_id / author_source on every
board write, from the caller's run token and never from the request body.

Covers ``runner/provenance.py::stamp`` / ``system_stamp``, ``/comms/post`` end to end, the
server-internal writers (``system``), and two source scans that keep a new writer from being
forgotten: ``add_comms_provenance`` relabels every row left with a NULL ``author_source`` as
``legacy`` on each start, so a writer that skips the stamp would hide as ``legacy``.
"""

from __future__ import annotations

import ast
import logging
import re

import pytest
from _paths import SRC

PKG = SRC / "pathly_orchestrator"


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


# ── source scans ───────────────────────────────────────────────────────────────


def _call_name(node):
    f = node.func
    return getattr(f, "id", None) or getattr(f, "attr", None)


def _passes_stamp(call):
    for kw in call.keywords:
        if kw.arg == "author_source":
            return True
        if (
            kw.arg is None
            and isinstance(kw.value, ast.Call)
            and (_call_name(kw.value) or "").endswith("stamp")
        ):
            return True
    return False


def _post_message_calls(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.Call)
        and _call_name(n) in ("post_message", "_post_message")
    ]


def _unstamped(path):
    return [c for c in _post_message_calls(path) if not _passes_stamp(c)]


def test_every_post_message_call_in_supervisor_and_runner_passes_a_stamp():
    seen = 0
    missing = []
    for sub in ("supervisor", "runner"):
        for path in sorted((PKG / sub).rglob("*.py")):
            calls = _post_message_calls(path)
            seen += len(calls)
            missing += [f"{path.relative_to(PKG)}:{c.lineno}" for c in _unstamped(path)]
    assert seen >= 4, "the scan found almost no post_message calls; it is not looking"
    assert not missing, f"post_message without a stamp: {missing}"


# Files whose post_message calls rely on the `none` default instead of an explicit stamp.
# Each is listed with the reason; the test below fails if a file here stops needing the entry,
# so the list can only shrink.
_UNSTAMPED_ALLOW = {
    # Size-frozen by scripts/check_file_size.py (over 400 lines): a stamp argument would grow
    # them. Their posts are board lifecycle status lines for UI-started runs, `none` for now.
    "http_server/blueprints/comms/goals.py",
    "http_server/blueprints/comms/project.py",
    "http_server/blueprints/comms/settings.py",
    # Written for a caller that is a human in the UI (no run token until RRP-2b) or a
    # promotion whose copy is a decision/constraint, which no policy withholds.
    "db/queries/comms_messages.py",
    "db/queries/comms_promote.py",
}


def test_every_post_message_call_is_stamped_or_on_the_allow_list():
    unlisted = []
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG).as_posix()
        if rel not in _UNSTAMPED_ALLOW and _unstamped(path):
            unlisted += [f"{rel}:{c.lineno}" for c in _unstamped(path)]
    assert (
        not unlisted
    ), f"post_message without a stamp, not on the allow-list: {unlisted}"


def test_the_allow_list_has_no_stale_entries():
    stale = [rel for rel in _UNSTAMPED_ALLOW if not _unstamped(PKG / rel)]
    assert not stale, f"no unstamped post_message call left in: {stale}"


_INSERT = re.compile(r"INSERT\s+(?:OR\s+\w+\s+)?INTO\s+(comms_messages|\{\})")

# Dynamic-table inserts that cannot name author_source in the statement. Each needs a reason.
_DYNAMIC_INSERT_ALLOW = {
    # Hydration copies a whole BOARD.json snapshot row, author_* columns included. A row from
    # an export made before the upgrade has none, stays NULL, and the startup backfill marks it
    # `legacy`, which is what it is. Rows exported after the upgrade carry their own value.
    "db/queries/comms_hydrate.py",
}


def _sql_strings(path):
    """Every string literal in the file; an f-string is rendered with `{}` for each field."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value
        elif isinstance(node, ast.JoinedStr):
            yield "".join(
                p.value if isinstance(p, ast.Constant) else "{}" for p in node.values
            )


def test_every_insert_into_comms_messages_sets_author_source():
    bad = []
    dynamic_files = set()
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG).as_posix()
        for sql in _sql_strings(path):
            m = _INSERT.search(sql)
            if not m:
                continue
            if m.group(1) == "{}":
                dynamic_files.add(rel)
            elif "author_source" not in sql:
                bad.append(rel)
    assert not bad, f"INSERT INTO comms_messages without author_source: {bad}"
    assert dynamic_files <= _DYNAMIC_INSERT_ALLOW, (
        f"dynamic-table INSERT not on the allow-list: "
        f"{sorted(dynamic_files - _DYNAMIC_INSERT_ALLOW)}"
    )
    assert dynamic_files == _DYNAMIC_INSERT_ALLOW, "stale _DYNAMIC_INSERT_ALLOW entry"


def test_the_insert_scan_sees_the_real_inserts():
    """Guard against the scan going blind: post_message's and the sentinel's INSERTs exist."""
    found = set()
    for path in sorted(PKG.rglob("*.py")):
        for sql in _sql_strings(path):
            if re.search(r"INSERT\s+INTO\s+comms_messages", sql):
                found.add(path.relative_to(PKG).as_posix())
    assert found == {
        "db/queries/comms_messages.py",
        "db/queries/comms_artifacts.py",
    }
