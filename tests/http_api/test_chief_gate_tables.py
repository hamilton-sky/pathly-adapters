"""chief-agent 08: the field table is complete and says what each route reads.

Walks ``app.url_map`` and the source of the views (and the helpers they call) so a route
or a request field added later cannot be added unbound.
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


_FIELD_READ = re.compile(
    r"""(?:\bdata|\bbody|args|payload)(?:\.get(?:list)?\(\s*|\[\s*)["']([A-Za-z_]+)["']"""
)
_PROJECT_ISH = re.compile(
    r"root|scope|board|project|feature|path|target|topic|_id$|slug"
)
_PATH_CALLS = {"join", "joinpath", "Path", "makedirs", "mkdir", "open"}
_HELPER_PACKAGE = "pathly_orchestrator.http_server.blueprints"


def _called_functions(function):
    """The functions under ``blueprints/`` that ``function`` calls by name: a module-level name,
    or one it imports inside its body (the layer rule keeps the imports lazy).
    """
    import ast
    import importlib
    import importlib.util
    import inspect
    import textwrap

    try:
        tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    except (OSError, TypeError):
        return
    package = function.__module__.rpartition(".")[0]
    imported = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = importlib.util.resolve_name(
                "." * node.level + (node.module or ""), package
            )
            for alias in node.names:
                imported[alias.asname or alias.name] = (module, alias.name)
    called = {
        n.func.id
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    for name in called:
        if name in imported:
            module, attr = imported[name]
            target = (
                getattr(importlib.import_module(module), attr, None)
                if module.startswith(_HELPER_PACKAGE)
                else None
            )
        else:
            target = function.__globals__.get(name)
        if inspect.isfunction(target) and target.__module__.startswith(_HELPER_PACKAGE):
            yield target


def _view_and_helpers(app, rule_text: str, method: str):
    """``(function, source)`` for each view of the route and every helper it calls (3 levels)."""
    import inspect
    import textwrap

    seen: set = set()

    def walk(function, depth):
        if function in seen or depth < 0:
            return
        seen.add(function)
        try:
            yield function, textwrap.dedent(inspect.getsource(function))
        except (OSError, TypeError):
            return
        for helper in _called_functions(function):
            yield from walk(helper, depth - 1)

    for rule in app.url_map.iter_rules():
        if rule.rule == rule_text and method in rule.methods:
            yield from walk(inspect.unwrap(app.view_functions[rule.endpoint]), 3)


def test_a_view_and_the_helpers_it_calls_read_no_project_ish_field_its_entry_does_not_name(
    app,
):
    """A tripwire, not a proof: it reads the source of the view and of the functions under
    ``blueprints/`` it calls (``create_run``, ``handle_retry``, ``_dispatch_*``), for the request
    fields they read by ``.get("name")`` or ``["name"]``. A helper that reads its inputs under
    another variable name, or a callee outside ``blueprints/``, is not seen.
    """
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    undeclared = {}
    for (rule_text, method), fields in ROUTE_FIELDS.items():
        for function, source in _view_and_helpers(app, rule_text, method):
            read = {k for k in _FIELD_READ.findall(source) if _PROJECT_ISH.search(k)}
            if read - fields.declared():
                undeclared.setdefault((rule_text, method), {})[function.__name__] = (
                    sorted(read - fields.declared())
                )

    assert undeclared == {}, f"views read fields the table does not name: {undeclared}"


def test_the_walk_reaches_the_helpers_the_views_call(app):
    names = {
        f.__name__
        for rule, method in (
            ("/runs", "POST"),
            ("/runs/<run_id>/<action>", "POST"),
            ("/comms/features/decompose", "POST"),
        )
        for f, _ in _view_and_helpers(app, rule, method)
    }

    assert {"create_run", "_create_flow_run", "handle_retry"} <= names
    assert {"_dispatch_board_run", "_dispatch_consultation"} <= names


def _joined_into_a_path(source: str) -> set[str]:
    """The names used as an argument of a path-building call (``os.path.join``, ``Path``,
    ``makedirs``, ``open``, ...) or of a ``/``: where a request value becomes part of a path.
    """
    import ast

    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        parts: list = []
        if isinstance(node, ast.Call):
            func = node.func
            name = (
                func.attr
                if isinstance(func, ast.Attribute)
                else getattr(func, "id", "")
            )
            if name in _PATH_CALLS:
                parts = list(node.args)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            parts = [node.left, node.right]
        found.update(
            sub.id
            for part in parts
            for sub in ast.walk(part)
            if isinstance(sub, ast.Name)
        )
    return found


def test_a_request_field_a_view_or_helper_joins_into_a_path_is_declared_as_one(app):
    """A tripwire for round 3 finding 2: ``feature`` was listed as an id (a board name) while the
    route joined it into ``<project_root>/pathly/features/<feature>``. A field of the entry that a
    view or helper uses as an argument of a path call must be a file (``paths``, ``abs_paths``)
    or a folder name (a ``segment`` scope, or a ``segments`` field). The match is by variable
    name, so it sees a helper that keeps the request's name for the value, as these do.
    """
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    undeclared = {}
    for (rule_text, method), fields in ROUTE_FIELDS.items():
        path_safe = {
            *fields.paths,
            *fields.abs_paths,
            *fields.segments,
            "project_root",
        }
        for read in fields.scopes:
            if read.segment:
                path_safe.update(read.keys)
        for function, source in _view_and_helpers(app, rule_text, method):
            joined = _joined_into_a_path(source) & fields.declared() - path_safe
            if joined:
                undeclared.setdefault((rule_text, method), {})[function.__name__] = (
                    sorted(joined)
                )

    assert (
        undeclared == {}
    ), f"a path is built from fields the table calls ids: {undeclared}"


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
