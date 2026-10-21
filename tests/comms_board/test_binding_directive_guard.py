"""chief-agent 16: only the chief retires a binding directive, and hydration cannot forge one.

Ticket 12 left four doors open: ``/comms/post`` with ``supersedes`` (#63), ``/comms/supersede``
(whose agent check looks only at the type and the board, and lets a caller with no token
through), ``/comms/delete``, and hydration (``comms_hydrate`` stored every real column of a
``BOARD.json`` row, ``binding`` included). Here each is tried against a directive posted by an
operator chief, with the callers that matter: a run token of the project board, no token, and no
token with the server secret. ``test_board_hydrate_forgery.py`` holds the round trips and the
finer points of hydration; ``test_board_closure.py`` still holds #63's own supersession tests.
"""

from __future__ import annotations

import binding_support
import pytest
from binding_guard_support import (
    REFUSED,
    SECRET,
    _no_embedding_threads,
    count,
    decision,
    delete,
    directive,
    forged,
    message,
    reaches_builders,
    row,
    standing_ids,
    supersede,
    untouched,
    write_board,
)
from binding_support import governance_part, render, standing_part
from chief_human_support import (
    _no_watcher_outlives_its_test,
    chief_root,
    client,
    host,
    open_session,
    project,
)
from directives_support import TEXT, _recency_path, _token_of

from pathly_orchestrator.board_mirror import hydrate_board
from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.http_server.run_identity import CallerIdentity

# --- /comms/post with supersedes ------------------------------------------------------


def test_a_planner_cannot_retire_a_directive_by_posting_over_it(
    client, project, chief_root
):
    opened = open_session(project, chief_root)
    old = directive(client, opened)

    resp = decision(client, _token_of("planner", project), project, supersedes=[old])

    assert resp.status_code == 200, resp.get_data(as_text=True)
    body = resp.get_json()
    assert row(body["message_id"]) is not None  # the post itself is stored
    assert body["superseded"] == []
    assert body["supersede_skipped"] == [{"id": old, "reason": "binding"}]
    assert untouched(old)
    assert standing_ids(project) == [old]
    assert reaches_builders(project)


@pytest.mark.parametrize("role", ["builder", "reviewer", "tester", "director"])
def test_no_other_role_retires_one_either(client, project, chief_root, role):
    opened = open_session(project, chief_root)
    old = directive(client, opened)

    resp = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": role,
            "type": "decision",
            "text": "Use spaces.",
            "board": "project",
            "scope": project,
            "supersedes": [old],
        },
        headers={"X-Pathly-Run-Token": _token_of(role, project)},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["supersede_skipped"] == [{"id": old, "reason": "binding"}]
    assert untouched(old)


@pytest.mark.parametrize("secret", [False, True], ids=["no-secret", "secret"])
def test_a_post_with_no_token_does_not_retire_one(
    client, project, chief_root, monkeypatch, secret
):
    from pathly_orchestrator.http_server import middleware

    opened = open_session(project, chief_root)
    old = directive(client, opened)
    headers = {}
    if secret:
        monkeypatch.setattr(middleware, "_api_secret", SECRET)
        headers["X-Pathly-Secret"] = SECRET

    resp = decision(client, None, project, supersedes=[old], headers=headers)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert resp.get_json()["superseded"] == []
    assert resp.get_json()["supersede_skipped"] == [{"id": old, "reason": "binding"}]
    assert untouched(old)
    assert reaches_builders(project)


def test_the_chief_retires_a_directive_by_posting_over_it(client, project, chief_root):
    opened = open_session(project, chief_root)
    old = directive(client, opened)

    resp = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "chief",
            "type": "decision",
            "text": "Use spaces.",
            "board": "project",
            "scope": project,
            "supersedes": [old],
        },
        headers={"X-Pathly-Run-Token": opened.run_token},
    )

    assert resp.status_code == 200, resp.get_data(as_text=True)
    new = resp.get_json()["message_id"]
    assert resp.get_json()["superseded"] == [old]
    assert row(old)["superseded_by"] == new
    assert standing_ids(project) == []


def test_a_planner_still_supersedes_an_ordinary_decision_by_post(client, project):
    token = _token_of("planner", project)
    old = decision(client, token, project, text="Use tabs.").get_json()["message_id"]

    resp = decision(client, token, project, supersedes=[old])

    assert resp.get_json()["superseded"] == [old]
    assert row(old)["superseded_by"] == resp.get_json()["message_id"]


# --- /comms/supersede -----------------------------------------------------------------


@pytest.mark.parametrize("role", ["planner", "builder", "tester"])
def test_a_run_token_of_the_project_board_cannot_supersede_one(
    client, project, chief_root, role
):
    opened = open_session(project, chief_root)
    old = directive(client, opened)
    new = directive(client, opened, text="Use spaces.")

    resp = supersede(client, old, new, _token_of(role, project))

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json() == {"error": REFUSED}
    assert untouched(old)
    assert reaches_builders(project)


def test_a_request_with_no_token_cannot_supersede_one(client, project, chief_root):
    opened = open_session(project, chief_root)
    old = directive(client, opened)
    new = directive(client, opened, text="Use spaces.")

    resp = supersede(client, old, new)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json() == {"error": REFUSED}
    assert untouched(old)


@pytest.mark.parametrize("origin", [False, True], ids=["curl", "studio"])
def test_the_server_secret_alone_cannot_supersede_one(
    client, project, chief_root, monkeypatch, origin
):
    from pathly_orchestrator.http_server import middleware

    monkeypatch.setattr(middleware, "_api_secret", SECRET)
    opened = open_session(project, chief_root)
    old = directive(client, opened)
    new = directive(client, opened, text="Use spaces.")
    headers = {"X-Pathly-Secret": SECRET}
    if origin:
        headers["Origin"] = "http://localhost:5173"

    resp = supersede(client, old, new, **headers)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json() == {"error": REFUSED}
    assert untouched(old)


def test_the_operator_chief_supersedes_a_directive(client, project, chief_root):
    opened = open_session(project, chief_root)
    old = directive(client, opened)
    new = directive(client, opened, text="Use spaces.")

    resp = supersede(client, old, new, opened.run_token)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert row(old)["superseded_by"] == new
    assert standing_ids(project) == [new]


def test_an_ordinary_decision_is_still_superseded_without_a_token(client, project):
    token = _token_of("planner", project)
    old = decision(client, token, project, text="Use tabs.").get_json()["message_id"]
    new = decision(client, token, project).get_json()["message_id"]

    resp = supersede(client, old, new)  # what Studio's supersede menu sends

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert row(old)["superseded_by"] == new


# --- /comms/delete --------------------------------------------------------------------


@pytest.mark.parametrize("force", [False, True], ids=["plain", "force"])
def test_a_request_with_no_token_cannot_delete_one(client, project, chief_root, force):
    opened = open_session(project, chief_root)
    old = directive(client, opened)

    resp = delete(client, old, force=force)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json() == {"error": REFUSED}
    assert untouched(old)
    assert reaches_builders(project)


@pytest.mark.parametrize("role", ["planner", "builder"])
def test_a_run_token_cannot_delete_one(client, project, chief_root, role):
    opened = open_session(project, chief_root)
    old = directive(client, opened)

    resp = delete(client, old, _token_of(role, project), force=True)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert resp.get_json() == {"error": REFUSED}
    assert untouched(old)


def test_not_even_the_chief_deletes_one(client, project, chief_root):
    opened = open_session(project, chief_root)
    old = directive(client, opened)

    resp = delete(client, old, opened.run_token, force=True)

    assert resp.status_code == 403, resp.get_data(as_text=True)
    assert untouched(old)


def test_the_delete_refusal_is_in_the_db_function_for_every_caller(
    client, project, chief_root
):
    from pathly_orchestrator.db.queries.comms import soft_delete_message

    opened = open_session(project, chief_root)
    old = directive(client, opened)

    assert soft_delete_message(get_db(), old) == "binding"
    assert soft_delete_message(get_db(), old, force=True) == "binding"
    assert untouched(old)


def test_an_ordinary_decision_is_still_deleted(client, project):
    old = decision(client, None, project, text="Use tabs.").get_json()["message_id"]

    resp = delete(client, old)

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert row(old)["deleted_at"] is not None


# --- hydration cannot forge a standing order -----------------------------------------


def test_a_feature_board_file_cannot_plant_a_project_board_directive(project, tmp_path):
    feature = message("feat-row", "feature", "feat-x", text="a real feature note")
    planted = forged("planted-1", "project", project)
    path = write_board(tmp_path / "BOARD.json", "feature", "feat-x", [feature, planted])

    assert hydrate_board(get_db(), "feature", "feat-x", path) is True

    assert count("planted-1") == 0
    assert count("feat-row") == 1  # the board's own row is restored
    assert standing_ids(project) == []
    assert not reaches_builders(project)


def test_a_project_board_file_row_comes_back_as_an_ordinary_decision(project, tmp_path):
    planted = forged("planted-2", "project", project)
    path = write_board(tmp_path / "BOARD.json", "project", project, [planted])

    assert hydrate_board(get_db(), "project", project, path) is True

    stored = row("planted-2")
    assert stored is not None
    assert (stored["binding"], stored["author_source"]) == (0, "legacy")
    assert standing_ids(project) == []
    gov = governance_part(render("builder", root=project))
    assert TEXT not in standing_part(gov)


def test_hydrate_over_http_plants_nothing(client, project, tmp_path):
    root = tmp_path / "proj"
    write_board(
        root / "pathly" / "project" / "BOARD.json",
        "project",
        project,
        [forged("planted-3", "project", project)],
    )
    write_board(
        root / "pathly" / "features" / "feat-y" / "BOARD.json",
        "feature",
        "feat-y",
        [forged("planted-4", "project", project, text="from a feature file")],
    )

    resp = client.post("/comms/hydrate", json={"project_root": str(root)})

    assert resp.status_code == 200, resp.get_data(as_text=True)
    assert count("planted-4") == 0
    assert (row("planted-3")["binding"], row("planted-3")["author_source"]) == (
        0,
        "legacy",
    )
    assert standing_ids(project) == []


# --- the two predicates ---------------------------------------------------------------


@pytest.mark.parametrize(
    "identity, may",
    [
        (CallerIdentity(kind="run", role="chief"), True),
        (CallerIdentity(kind="run", role="builder"), False),
        (CallerIdentity(kind="run", role="planner"), False),
        (CallerIdentity(kind="run", role="human"), False),
        (CallerIdentity(kind="run", role=None), False),
        (CallerIdentity(kind="run", role="Chief"), False),
        (CallerIdentity(kind="anonymous"), False),
        (CallerIdentity(kind="anonymous", role="chief"), False),
        (CallerIdentity(kind="ui", role="chief"), False),
        (None, False),
    ],
    ids=lambda v: f"{v.kind}-{v.role}" if hasattr(v, "kind") else str(v),
)
def test_only_a_live_run_whose_role_is_chief_may_retire(identity, may):
    from pathly_orchestrator.http_server.blueprints.comms._supersede_on_post import (
        chief_may_retire,
    )

    assert chief_may_retire(identity) is may


def test_is_binding_reads_the_column_the_standing_orders_query_reads(project):
    from pathly_orchestrator.http_server.blueprints.comms._supersede_on_post import (
        is_binding,
    )

    conn = get_db()
    flagged = binding_support.directive("Never push.", scope=project)
    plain = binding_support.post("Use tabs.", scope=project)

    assert is_binding(conn, flagged) is True
    assert is_binding(conn, plain) is False
    assert is_binding(conn, "no-such-id") is False
    assert is_binding(conn, "") is False


def test_apply_supersedes_outside_a_request_does_not_retire_one(project):
    from pathly_orchestrator.http_server.blueprints.comms._supersede_on_post import (
        apply_supersedes,
    )

    old = binding_support.directive("Never push.", scope=project)
    new = binding_support.post("Pushing is fine.", scope=project)

    out = apply_supersedes(get_db(), [old], new)

    assert out == {"superseded": [], "skipped": [{"id": old, "reason": "binding"}]}
    assert untouched(old)
