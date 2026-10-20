"""chief-agent 08 (rounds 6 and 7): a chief that sends hostile values touches nothing outside its
project.

The earlier rounds read the code for the places a request string becomes a path and listed them.
This test does not rely on that list. It runs the server for real (the spawn host is faked, the
database is the test's), puts every key a chief may send to every route through hostile values,
as a status, a planner and an operator chief, and records every file system call the process
makes (``chief_audit_support``). It asserts that none fell in another project's tree, the server's
working directory or the home directory.

What is sent to which key, at every tier (``hostile_values``, ``PLAIN_VALUES``):

* a key of a kind that can reach a file or a folder (``chief_field_types.FILE_KINDS``: root,
  scope, segment, path, ref, flow, skill) gets the **whole** list: climbing and absolute paths,
  other project, server directory, home, UNC and drive spellings, a NUL, a very long name, and the
  spellings of the chief's own root and of its own file (trailing and doubled slashes, dot
  segments, backslashes, mixed separators, padded) that the gate may accept as the chief's own;
* every other key (text, number, flag, enum, name, id) gets ``PLAIN_VALUES``: a climbing path in
  both relative and absolute form, another project, another project's file, a NUL, a very long
  name.

The static tests (``test_chief_gate_keys.py``, ``test_chief_gate_kinds.py``) hold the other half:
the list of keys is complete and a key's kind fits what its view does with it. What this one
cannot see is in ``chief_audit_support``'s docstring (a probe with ``os.stat`` is not an audit
event), and it only sends the requests ``chief_audit_calls`` and ``chief_audit_reads`` build: a
route reached by none of them is only as deep as its first check. ``REACHES`` names the baselines
that are asserted to get to the work their route exists for.
"""

from __future__ import annotations

import os

import pytest
from chief_audit_sandbox import drain_the_mirrors, world
from chief_audit_support import Audit, Touch
from chief_audit_world import DEMO, World, settle
from chief_gate_support import (
    _chief,
    _gated,
    _no_code_backend,
    _no_reindex,
    _streams_do_not_block,
    app,
    client,
    other_project,
    project,
)

TIERS = ("operator", "planner", "status")


def hostile_values(world: World) -> dict[str, str]:
    other, server, home = world.other, world.server, world.project.parent
    own, plan = str(world.project), str(world.plan)
    return {
        "dotdot": "..",
        "relative climbing": "../..",
        "climbing": "../../../../proj-b/planted",
        "other project": str(other),
        "other file": f"{other}/pathly/features/{DEMO}/PLAN.md",
        "server dir": f"{server}/planted",
        "home dir": f"{home}/planted",
        "unc": "//host/share/planted",
        "unc backslash": "\\\\host\\share\\planted",
        "drive": "C:\\planted",
        "nul": "x\0y",
        "trailing slash": "x/",
        "very long": "a" * 5000,
        # The chief's own root and file, spelled so that a gate which reads them as the same
        # directory might let them through: the routes open the raw string, so each must name the
        # same directory there, or be refused.
        "own root, trailing slash": own + "/",
        "own root, doubled trailing slash": own + "//",
        "own root, dot segment": own + "/.",
        "own root, dot in the middle": own.replace(
            world.project.name, "./" + world.project.name
        ),
        "own root, doubled slashes": own.replace("/", "//"),
        "own root, backslash at the end": own + "\\",
        "own root, backslashes": own.replace("/", "\\"),
        "own root, mixed separators": f"{home}\\{world.project.name}",
        "own root, climbing with backslashes": f"{own}/sub\\..\\..\\{other.name}",
        "own root, padded": f" {own}",
        "own file, backslashes": plan.replace("/", "\\"),
        "own file, dot segments and doubled slashes": f"{own}/./pathly//features/{DEMO}/PLAN.md",
        "own file, padded": f" {plan}",
    }


# A key that is only text, a number or a name is never joined into a path by design, and a status
# or a planner chief reaches the same code after the gate: these values show it (the relative
# and the absolute climbing path are the two ways a join leaves its folder).
PLAIN_VALUES = (
    "dotdot",
    "relative climbing",
    "climbing",
    "other project",
    "other file",
    "nul",
    "very long",
)


def _routes(app):
    """``(rule, method, [(key, kind)])`` for every route of the table the app has: the keys a
    chief may send and the variables of its URL. ``kind`` is ``"plain"`` for a key that names no
    file, the file kind of one that can, and None for a URL variable the entry does not name.
    """
    from pathly_orchestrator.http_server.chief_field_types import (
        FILE_KINDS,
        url_variables,
    )
    from pathly_orchestrator.http_server.chief_fields import ROUTE_FIELDS

    live = {
        (rule.rule, method)
        for rule in app.url_map.iter_rules()
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }
    for (rule, method), fields in sorted(ROUTE_FIELDS.items()):
        if (rule, method) not in live:
            continue
        kinds = fields.kinds()
        keys = []
        for key in sorted(fields.allowed(rule) | url_variables(rule)):
            kind = kinds.get(key)
            keys.append((key, kind if kind in FILE_KINDS or kind is None else "plain"))
        yield rule, method, keys


def test_every_url_variable_gets_the_whole_list(app):
    """The short list is for a key that is only text. A variable of the URL (a feature, a run or
    an artifact id) is joined into a path or a query by the route, whatever the entry calls it,
    so it gets the same values as a key of a file kind. Round 7 found the ``feature`` of eight
    rules, the ``artifact_id`` of one and the ``run_id`` of four on the short list.
    """
    from pathly_orchestrator.http_server.chief_field_types import url_variables

    variables, short = [], []
    for rule, method, keys in _routes(app):
        kinds = dict(keys)
        for variable in sorted(url_variables(rule)):
            variables.append((rule, method, variable))
            if kinds[variable] == "plain":
                short.append((rule, method, variable))

    assert variables, "the table lists no route with a variable in its URL"
    assert short == [], f"URL variables on the short list: {short}"


def _attack(env, app, tier: str) -> dict:
    """Send the hostile values in every key of every route; return how the routes answered."""
    world, audit = env.world, env.audit
    chief = _chief(tier, world.project)
    named = hostile_values(world)
    every, few = list(named.values()), [named[n] for n in PLAIN_VALUES]
    answers: dict[str, int] = {}
    for rule, method, keys in _routes(app):
        for variant in world.variants(rule, method):
            for key, kind in keys:
                for value in few if kind == "plain" else every:
                    audit.label = (
                        f"{tier} {method} {rule} [{variant.label}] {key}={value[:40]!r}"
                    )
                    resp = world.request(
                        rule, method, variant, key, value, chief.headers
                    )
                    answer = "gated" if _gated(resp) else str(resp.status_code)
                    answers[answer] = answers.get(answer, 0) + 1
                    settle()
    audit.label = f"{tier} (the mirrors)"
    drain_the_mirrors()
    return answers


def _report(audit: Audit) -> str:
    """The touches, one line for each distinct call (the first request that made it)."""
    first: dict[tuple[str, str], Touch] = {}
    for touch in audit.violations:
        first.setdefault((touch.event, touch.path), touch)
    return f"{len(audit.violations)} touches outside the project:\n" + "\n".join(
        f"{t.label}\n    {t.event} {t.path}" for t in list(first.values())[:40]
    )


@pytest.mark.parametrize("tier", TIERS)
def test_a_chief_touches_nothing_outside_its_project(world, app, tier):
    answers = _attack(world, app, tier)

    assert world.audit.violations == [], _report(world.audit)
    # The run was not vacuous: requests got past the gate, and the audit saw the project's tree.
    assert answers.get("200", 0) > 20, answers
    assert answers.get("gated", 0) > 20, answers
    assert world.audit.seen, "the audit saw no call in the chief's own project"


# --- the audit can see what it is there to see ---------------------------------------------


def test_the_audit_sees_a_call_in_each_zone_and_ignores_the_projects_own(world):
    import sqlite3
    import subprocess

    w, audit = world.world, world.audit
    audit.violations.clear()

    (w.other / "a.txt").write_text("x")  # open for writing, in another project
    (w.other / "sub").mkdir()  # mkdir
    os.rename(w.other / "a.txt", w.other / "b.txt")  # rename
    os.remove(w.other / "b.txt")  # remove
    os.listdir(w.server)  # a read of the server's directory
    (w.project.parent / "stray").write_text("x")  # the home directory
    sqlite3.connect(str(w.other / "x.db")).close()  # a database file
    subprocess.run(["true"], cwd=w.other, check=True)  # a child process
    os.listdir()  # no argument: the working directory, which is the server's

    events = {t.event for t in audit.violations}
    assert {
        "open",
        "os.mkdir",
        "os.rename",
        "os.remove",
        "os.listdir",
        "sqlite3.connect",
        "subprocess.Popen",
    } <= events, events

    before = len(audit.violations)
    (w.project / "own.txt").write_text("x")
    (w.project.parent / ".pathly" / "own.txt").write_text("x")
    os.listdir(w.project)
    assert len(audit.violations) == before
    assert any(t.path.endswith("own.txt") for t in audit.seen)


def test_the_audit_sees_a_write_a_request_makes_in_another_project(world, client):
    """A caller with no token may name another project's root as a board's scope, and the board
    mirror then writes that project's ``BOARD.json``. The chief gate refuses the same call to a
    chief; this is the proof that the audit would have seen it if the gate did not.
    """
    w, audit = world.world, world.audit
    audit.violations.clear()
    body = {
        "board": "project",
        "feature": DEMO,
        "scope": str(w.other),
        "from": "human",
        "type": "status",
        "text": "a note on another project's board",
    }

    human = client.post("/comms/post", json=body)
    drain_the_mirrors()
    assert human.status_code == 200, human.get_data(as_text=True)
    assert any("BOARD.json" in t.path for t in audit.violations), _report(audit)

    audit.violations.clear()
    chief = _chief("operator", w.project)
    resp = client.post(
        "/comms/post", json={**body, "from": "chief"}, headers=chief.headers
    )
    drain_the_mirrors()
    assert _gated(resp)
    assert audit.violations == [], _report(audit)


def _answered(**wanted):
    """A check: the route answered 2xx and its JSON body has each of ``wanted``."""

    def check(resp) -> bool:
        body = resp.get_json(silent=True) or {}
        return resp.status_code < 300 and all(
            body.get(k) == v for k, v in wanted.items()
        )

    return check


def _queried(resp) -> bool:
    """``/code/query`` got through the canned ``cli`` backend and back with a block."""
    body = resp.get_json(silent=True) or {}
    return (
        resp.status_code == 200
        and body.get("backend") == "cli"
        and "a_function" in (body.get("result") or "")
    )


# The routes whose valid request must get to the work the route exists for, and how to tell:
# a 2xx for most, and for the ones that used to stop at "nothing to do" (a stop with no run
# held, a supersede the route refuses for another board's decision, an answer with no question
# open, a query that stops at "backend none") the answer that says the work was done.
# Not here, because the audit's request stops before the sink: ``reroute`` (it sets an attribute
# of a registered run) and ``retry`` (it starts the run, whose loop the audit replaces with one
# that finishes at once), and the codeintel, lsp and both backends of ``/code/query`` (they need
# an external tool).
REACHES = {
    ("/comms/post", "POST"): _answered(),
    ("/comms/goals/run", "POST"): _answered(),
    ("/comms/goals/decompose", "POST"): _answered(),
    ("/comms/features/decompose", "POST"): _answered(),
    ("/comms/project/decompose", "POST"): _answered(),
    ("/comms/run", "POST"): _answered(),
    ("/comms/tasks/run", "POST"): _answered(),
    ("/comms/answer", "POST"): _answered(),
    ("/comms/acknowledge", "POST"): _answered(),
    ("/runs", "POST"): _answered(),
    ("/runs/<run_id>/<action>", "POST"): _answered(),
    ("/comms/artifacts/<artifact_id>/section", "GET"): _answered(),
    ("/comms/artifacts/section", "GET"): _answered(),
    ("/comms/supersede", "POST"): _answered(ok=True),
    ("/runner/agent-answer", "POST"): _answered(status="accepted"),
    ("/runs/<run_id>/stop", "POST"): _answered(stopped=True),
    ("/comms/goals/stop", "POST"): _answered(stopped=True),
    ("/comms/run/stop", "POST"): _answered(stopped=True),
    ("/comms/tasks/stop", "POST"): _answered(stopped=True),
    ("/code/query", "POST"): _queried,
}


def test_the_requests_the_audit_starts_from_are_valid_ones(world, client):
    """Each baseline in ``REACHES`` is accepted by its route and gets to its work, so the
    hostile value is the only thing wrong with the request the audit sends. (The one that asks
    for another project's artifact is refused by the route: that refusal is what it is there to
    show.)
    """
    w = world.world
    chief = _chief("operator", w.project)
    refused = {}
    for rule, method, _keys in _routes(client.application):
        reached = REACHES.get((rule, method))
        if reached is None:
            continue
        for variant in w.variants(rule, method):
            resp = w.request(
                rule, method, variant, "project_root", str(w.project), chief.headers
            )
            settle()
            if variant.label == "another project's":
                assert resp.status_code == 400, resp.get_data(as_text=True)
                assert resp.get_json()["error"] == "path_out_of_scope"
            elif not reached(resp):
                refused[(rule, method, variant.label)] = (
                    resp.status_code,
                    resp.get_data(as_text=True)[:120],
                )

    assert refused == {}
