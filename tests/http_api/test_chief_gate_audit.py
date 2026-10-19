"""chief-agent 08 (round 6): a chief that sends hostile values touches nothing outside its project.

The earlier rounds read the code for the places a request string becomes a path and listed them.
This test does not rely on that list. It runs the server for real (the spawn host is faked, the
database is the test's), puts every key a chief may send to every route through hostile values
(``..``, a climbing path, an absolute path into another project, into the server's directory and
into the home directory, a UNC path, a drive letter, a NUL, a trailing slash, a very long name), as
a status, a planner and an operator chief, and records every file system call the process makes
(``chief_audit_support``). It asserts that none fell in another project's tree, the server's
working directory or the home directory.

The static test (``test_chief_gate_keys.py``) holds the other half: the list of keys is complete.
What this one cannot see is in ``chief_audit_support``'s docstring (a probe with ``os.stat`` is
not an audit event), and it only sends the requests ``chief_audit_world`` builds: a route reached
by none of them is only as deep as its first check.
"""

from __future__ import annotations

import os
import sys
import time
from types import SimpleNamespace

import pytest
from chief_audit_support import Audit, zones
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
    return {
        "dotdot": "..",
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
    }


# A key that is only text, a number or a name is never joined into a path by design, and a status
# or a planner chief reaches the same code after the gate: a few values show it.
FEWER = ("dotdot", "other project", "other file", "nul", "very long")


@pytest.fixture()
def world(app, client, project, other_project, tmp_path, monkeypatch):
    """Three directories, a seeded board, a spawn host that spawns nothing, and the audit."""
    server = tmp_path / "server"
    server.mkdir()
    (other_project / "pathly" / "features" / DEMO).mkdir(parents=True)
    (other_project / "pathly" / "features" / DEMO / "PLAN.md").write_text("# other\n")
    # A relative entry of sys.path would make a lazy import search the server's directory.
    monkeypatch.setattr(sys, "path", [os.path.abspath(p or ".") for p in sys.path])
    monkeypatch.chdir(server)
    # A view that raises on a hostile value answers 500 as it does in production; the test
    # client would raise it into the test instead.
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)

    from pathly_orchestrator.supervisor import board_lock, file_claims, registry

    board_lock._held.clear()
    registry._registry.clear()
    monkeypatch.setattr(file_claims, "_claims", {})
    monkeypatch.setattr(
        "pathly_orchestrator.supervisor.board_run._default_spawn",
        lambda **kwargs: {"result": "a real analysis of the board"},
    )
    monkeypatch.setattr(
        "pathly_orchestrator.http_server.sse._broadcast_runner", lambda *a, **k: None
    )

    def loop(state, broadcast_fn=None):
        state.status = "done"

    monkeypatch.setattr("pathly_orchestrator.supervisor.orchestrator._loop", loop)

    audit = zones(project, other_project, server, tmp_path)
    audit.label = "seeding"
    with audit:
        built = World(client, project, other_project, server)
        # The seeding is a human's, who may write anywhere (a post indexes its artifact on a
        # background thread): only the chief's requests are judged.
        settle()
        time.sleep(0.3)
        audit.violations.clear()
        audit.seen.clear()
        yield SimpleNamespace(world=built, audit=audit)
        settle()
    board_lock._held.clear()
    registry._registry.clear()


def _drain_the_mirrors() -> None:
    """Let the debounced board and event mirrors write what they were asked to: flush, wait out
    one tick (a write the flusher thread took first finishes meanwhile), flush again.
    """
    from pathly_orchestrator import board_mirror, event_mirror
    from pathly_orchestrator.db.connection import get_db

    board_mirror.flush_dirty(get_db())
    event_mirror.flush_dirty(get_db())
    time.sleep(max(board_mirror.DEBOUNCE_SECONDS, event_mirror.DEBOUNCE_SECONDS) + 0.3)
    board_mirror.flush_dirty(get_db())
    event_mirror.flush_dirty(get_db())


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


def _attack(env, app, tier: str) -> dict:
    """Send the hostile values in every key of every route; return how the routes answered."""
    world, audit = env.world, env.audit
    chief = _chief(tier, world.project)
    named = hostile_values(world)
    every, few = list(named.values()), [named[n] for n in FEWER]
    answers: dict[str, int] = {}
    for rule, method, keys in _routes(app):
        for variant in world.variants(rule, method):
            for key, kind in keys:
                for value in few if tier != "operator" or kind == "plain" else every:
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
    _drain_the_mirrors()
    return answers


def _report(audit: Audit) -> str:
    return f"{len(audit.violations)} touches outside the project:\n" + "\n".join(
        f"{t.label}\n    {t.event} {t.path}" for t in audit.violations[:20]
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
    _drain_the_mirrors()
    assert human.status_code == 200, human.get_data(as_text=True)
    assert any("BOARD.json" in t.path for t in audit.violations), _report(audit)

    audit.violations.clear()
    chief = _chief("operator", w.project)
    resp = client.post(
        "/comms/post", json={**body, "from": "chief"}, headers=chief.headers
    )
    _drain_the_mirrors()
    assert _gated(resp)
    assert audit.violations == [], _report(audit)


# The routes whose valid request must get to the view's work (a 2xx).
MUST_BE_ACCEPTED = {
    ("/comms/post", "POST"),
    ("/comms/goals/run", "POST"),
    ("/comms/goals/decompose", "POST"),
    ("/comms/features/decompose", "POST"),
    ("/comms/project/decompose", "POST"),
    ("/comms/run", "POST"),
    ("/comms/tasks/run", "POST"),
    ("/comms/answer", "POST"),
    ("/comms/acknowledge", "POST"),
    ("/runs", "POST"),
    ("/runs/<run_id>/<action>", "POST"),
    ("/comms/artifacts/<artifact_id>/section", "GET"),
    ("/comms/artifacts/section", "GET"),
}


def test_the_requests_the_audit_starts_from_are_valid_ones(world, client):
    """Each baseline is accepted by its route, so the hostile value is the only thing wrong
    with the request the audit sends. (The one that asks for another project's artifact is
    refused by the route: that refusal is what it is there to show.)
    """
    w = world.world
    chief = _chief("operator", w.project)
    refused = {}
    for rule, method, _keys in _routes(client.application):
        if (rule, method) not in MUST_BE_ACCEPTED:
            continue
        for variant in w.variants(rule, method):
            resp = w.request(
                rule, method, variant, "project_root", str(w.project), chief.headers
            )
            settle()
            if variant.label == "another project's":
                assert resp.status_code == 400, resp.get_data(as_text=True)
                assert resp.get_json()["error"] == "path_out_of_scope"
            elif resp.status_code >= 300:
                refused[(rule, method, variant.label)] = resp.status_code

    assert refused == {}
