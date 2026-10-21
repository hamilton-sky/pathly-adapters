"""chief-agent 14 (contract): what ``target_in_project`` answers, and the table it reads.

The gate calls ``chief_bind.target_in_project(conn, session, rule, body, view_args)``. It says True
when every id the route's entry names is in the session's project, False when one is not, and None
when the route names none; a URL variable is read from the URL and never from the body. The
``ROUTE_FIELDS`` entries are the inventory of the ids it binds: this file pins the list.
"""

from __future__ import annotations

from types import SimpleNamespace

from chief_bind_support import feature_row, project_row, record_run
from chief_cite_support import db
from chief_gate_support import other_project, project


def test_target_in_project_says_true_false_or_none(project, other_project):
    from pathly_orchestrator.http_server.chief_bind import target_in_project

    session = {"project_root": str(project)}
    ours, theirs = project_row(project), project_row(other_project)
    record_run(project, "run-ours")
    stop = "/runs/<run_id>/stop"

    def ask(rule, body, view_args=None):
        return target_in_project(db(), session, rule, body, view_args or {})

    assert ask("/comms/acknowledge", {"message_id": ours}) is True
    assert ask("/comms/acknowledge", {"message_id": theirs}) is False
    assert ask("/comms/acknowledge", {"message_id": "unknown"}) is True
    assert ask("/comms/acknowledge", {}) is None
    assert ask("/comms/post", {"text": "plain"}) is None
    assert ask("/comms/post", {"goal_id": theirs}) is False
    assert ask("/comms/post", {"run_id": "run-gone"}) is True
    assert ask("/comms/supersede", {"old_id": ours, "new_id": theirs}) is False
    assert ask("/comms/search", {"goal_id": theirs}) is None
    assert ask("/not/a/route", {"message_id": theirs}) is None
    # A URL variable is read from the URL, never from the body.
    assert ask(stop, {}, {"run_id": "run-gone"}) is False
    assert ask(stop, {"run_id": "run-ours"}, {"run_id": "run-gone"}) is False
    assert ask(stop, {"run_id": "run-gone"}, {"run_id": "run-ours"}) is True


def test_a_session_with_no_usable_root_is_bound_to_nothing(project):
    from pathly_orchestrator.http_server.chief_bind import target_in_project

    # A feature row is answered by a folder of the project, which a session with no root has not.
    rows = [project_row(project), feature_row()]

    for root in (None, "", "proj\\a", 7):
        session = {"project_root": root}
        unknown = {"message_id": "unknown"}

        for known in rows:
            body = {"message_id": known}

            assert (
                target_in_project(db(), session, "/comms/acknowledge", body, {})
                is False
            )
        assert (
            target_in_project(db(), session, "/comms/acknowledge", unknown, {}) is True
        )


def test_the_table_lists_the_ids_chief_bind_binds_and_the_rest_as_unbound():
    from pathly_orchestrator.http_server.chief_field_types import ID
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    bound, left = set(), set()
    for (rule, method), fields in ROUTE_FIELDS.items():
        if method != "POST":
            continue
        named = (*fields.run_ids, *fields.stamped_run_ids, *fields.row_ids)
        bound |= {(rule, key) for key in named}
        left |= {(rule, key) for key in fields.unbound}
        for key in named:
            assert fields.kinds()[key] == ID, (rule, key)
            assert key not in fields.unbound, (rule, key)

    assert bound == {
        ("/runs/<run_id>/<action>", "run_id"),
        ("/runs/<run_id>/stop", "run_id"),
        ("/comms/post", "run_id"),
        ("/comms/post", "goal_id"),
        ("/comms/acknowledge", "message_id"),
        ("/comms/supersede", "old_id"),
        ("/comms/supersede", "new_id"),
        ("/comms/answer", "question_id"),
        ("/comms/goals/run", "goal_id"),
        ("/comms/goals/stop", "goal_id"),
        ("/comms/goals/decompose", "goal_id"),
        ("/runs", "goal_id"),
        ("/comms/tasks/run", "message_id"),
        ("/comms/tasks/stop", "message_id"),
    }
    # The topic of a run is checked by the cite rule (ticket 10); an option id is refused to a
    # chief by it.
    assert left == {("/runner/agent-answer", "topic"), ("/comms/answer", "option_id")}


def test_a_registry_entry_that_records_no_project_is_not_placed(project, monkeypatch):
    """A run the registry holds but cannot place in a project is refused, never an error."""
    from pathly_orchestrator.http_server.chief_bind import target_in_project
    from pathly_orchestrator.supervisor import registry

    odd = SimpleNamespace(run_id="run-odd", status="running")
    monkeypatch.setitem(registry._registry, "odd", odd)

    found = target_in_project(
        db(),
        {"project_root": str(project)},
        "/runs/<run_id>/stop",
        {},
        {"run_id": "run-odd"},
    )

    assert found is False
