"""chief-agent 08: the field table is complete and says what each route reads.

Walks ``app.url_map`` so a route added later cannot be added unbound. The keys of each route are
read against the source of its view and helpers in ``test_chief_gate_keys.py``.
"""

from __future__ import annotations

import re

from chief_gate_support import (
    NAMES_A_PROJECT,
    NAMES_A_PROJECT_READS,
    PLANNED,
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    project,
)
from chief_walk_support import view_and_helpers

# --- the table is complete, and says something about every route --------------------------


def _chief_reachable(app) -> set[tuple[str, str]]:
    """Every (rule, method) a chief token can get past the route table: the listed non-GET
    routes, and every GET that is not refused.
    """
    from pathly_orchestrator.http_server.chief_routes import ROUTE_ACTIONS, action_for

    found = set()
    for rule in app.url_map.iter_rules():
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            if method == "GET":
                if action_for(rule.rule, "GET", {}, {}, lambda _: False) is not None:
                    found.add((rule.rule, "GET"))
            elif (rule.rule, method) in ROUTE_ACTIONS:
                found.add((rule.rule, method))
    return found


def test_the_walk_finds_the_routes_a_chief_can_reach(app):
    reachable = _chief_reachable(app)

    assert {
        ("/comms", "GET"),
        ("/runs/<run_id>", "GET"),
        ("/db/stats", "GET"),
        ("/comms/post", "POST"),
        ("/code/query", "POST"),
        ("/runs/<run_id>/<action>", "POST"),
    } <= reachable
    assert ("/db/settings", "GET") not in reachable
    assert ("/events/spawn", "GET") not in reachable
    assert ("/db/query", "POST") not in reachable
    assert len(reachable) > 60


def test_every_route_a_chief_can_reach_says_which_fields_it_reads_as_a_project(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    missing = _chief_reachable(app) - set(ROUTE_FIELDS)

    assert not missing, (
        "a route the chief can reach has no entry in chief_fields.ROUTE_FIELDS "
        f"(list the project fields it reads, or say that it reads none): {sorted(missing)}"
    )


def test_the_field_table_lists_no_route_that_does_not_exist(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    stale = set(ROUTE_FIELDS) - _chief_reachable(app) - PLANNED

    assert (
        not stale
    ), f"the field table lists routes the chief cannot reach: {sorted(stale)}"


def test_an_entry_names_a_field_or_gives_a_reason(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    silent = [
        key
        for key, fields in ROUTE_FIELDS.items()
        if not fields.declared() and not fields.note.strip()
    ]

    assert silent == [], f"an entry that reads no project field must say why: {silent}"


def test_a_route_that_names_its_root_reads_one(app):
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    for key, fields in ROUTE_FIELDS.items():
        if (
            fields.names_root
            or fields.names_root_when
            or fields.names_root_unless
            or fields.names_root_verbs
        ):
            assert "project_root" in fields.roots, key


def test_every_route_that_starts_an_agent_in_a_directory_names_its_root():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS
    from pathly_orchestrator.http_server.chief_routes import (
        ROUTE_ACTIONS,
        RUN_VERB_ACTIONS,
    )

    # The stops name a run or a board by id (ticket 14) and start nothing. The one `run` route
    # that is addressed by a run id, `/runs/<run_id>/<action>`, starts an agent for `retry` only
    # (`start_run` in the directory its body names); its other verbs act on the registry's run.
    by_verb = "/runs/<run_id>/<action>"
    starts_one = {
        rule for (rule, _), action in ROUTE_ACTIONS.items() if action == "run"
    } | {rule for (rule, _) in ROUTE_ACTIONS if "decompose" in rule}
    names_root = {
        rule
        for (rule, method), f in ROUTE_FIELDS.items()
        if method != "GET" and (f.names_root or f.names_root_verbs)
    }

    assert names_root == starts_one | {"/code/query"}
    assert starts_one - {by_verb} == {p for p, _ in NAMES_A_PROJECT}
    verbs = ROUTE_FIELDS[(by_verb, "POST")].names_root_verbs
    assert verbs == ("retry",)
    assert {RUN_VERB_ACTIONS[v] for v in verbs} == {"run"}


def test_the_reads_that_name_their_root_are_the_ones_that_fall_back_to_another_project():
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    names_root = {
        rule
        for (rule, method), f in ROUTE_FIELDS.items()
        if method == "GET" and f.names_root
    }

    assert names_root == set(NAMES_A_PROJECT_READS)


def test_the_walk_reaches_the_helpers_the_views_call(app):
    names = {
        f.__name__
        for rule, method in (
            ("/runs", "POST"),
            ("/runs/<run_id>/<action>", "POST"),
            ("/comms/features/decompose", "POST"),
        )
        for f, _ in view_and_helpers(app, rule, method)
    }

    assert {"create_run", "_create_flow_run", "handle_retry"} <= names
    assert {"_dispatch_board_run", "_dispatch_consultation"} <= names


def test_the_segment_scopes_are_the_two_routes_that_make_a_folder_of_them():
    """A ``segment`` scope is for a route that joins the scope into a folder it makes. A scope
    that only reaches the board mirror is held by the rule every scope gets (a path is the
    chief's own root, anything else off the project board is one folder name) and by the
    mirror's own check, so it is not listed here.
    """
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    segments = {
        key
        for key, fields in ROUTE_FIELDS.items()
        if any(read.segment for read in fields.scopes)
    }

    assert segments == {
        ("/comms/features/decompose", "POST"),
        ("/comms/run", "POST"),
    }


def test_a_post_that_stores_a_slug_declares_it_a_folder_name():
    """``slug`` of a goal post is stored and later joined into ``goals/<slug>`` by the goal
    run and decompose, so the entry names it as a folder name, not an id."""
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    assert "slug" in ROUTE_FIELDS[("/comms/post", "POST")].segments


def test_a_listed_non_get_route_reads_the_body_and_a_get_route_reads_the_query(app):
    """The table applies to the body of a POST and the query string of a GET: no listed POST view
    reads ``request.args`` and no GET view reads a JSON body.
    """
    import inspect

    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    crossed = []
    for rule_text, method in ROUTE_FIELDS:
        for rule in app.url_map.iter_rules():
            if rule.rule != rule_text or method not in rule.methods:
                continue
            try:
                source = inspect.getsource(
                    inspect.unwrap(app.view_functions[rule.endpoint])
                )
            except (OSError, TypeError):
                continue
            if method != "GET" and "request.args" in source:
                crossed.append((rule_text, method, "reads the query string"))
            if method == "GET" and re.search(
                r"get_json|read_json_body|request\.json|get_data", source
            ):
                crossed.append((rule_text, method, "reads a body"))

    assert crossed == []


def test_a_route_with_no_entry_is_refused_not_passed(client, project, monkeypatch):
    chief = _chief("status", project)
    assert client.get("/comms?feature=demo", headers=chief.headers).status_code == 200
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.chief_project.ROUTE_FIELDS", {}
    )

    resp = client.get("/comms?feature=demo", headers=chief.headers)

    assert _gated(resp), (resp.status_code, resp.get_data(as_text=True)[:200])
    assert resp.get_json()["action"] == "read"
