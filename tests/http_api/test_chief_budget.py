"""chief-agent 15: what one chief session may spend and start.

An operator chief gets a ceiling on the cost one run may state (``chief.max_cost_usd_per_run``,
default 10) and a limit on the runs it may start (``chief.max_runs_per_session``, default 20),
both read from the app settings on every call. The ceiling is judged on ``POST /runs`` and on
``retry``, the two routes whose body carries ``max_cost_usd``. A call counts one run when the gate
lets it through and it is one that starts work (``POST /runs``, ``/comms/goals/run``,
``/comms/run``, ``/comms/tasks/run`` and the ``retry`` verb); the route's own 4xx gives the slot
back, a 2xx or a 5xx keeps it. Every case runs the real gate and routes; what would start an agent
is a stub. Hostile values, the settings parser, the refund hook and the race are in
``test_chief_budget_edges.py``.
"""

from __future__ import annotations

import sqlite3

import pytest
from chief_bind_support import _boards_are_free, project_row, stubs
from chief_budget_support import (
    CEILING_KEY,
    LIMIT_KEY,
    STARTS,
    finished_run,
    flow_runs,
    is_above,
    is_maxed,
    retry,
    runs_started,
    setting,
    shown,
    start_flow,
)
from chief_cite_support import builder_headers, db
from chief_gate_support import (
    _chief,
    _gated,
    app,
    client,
    other_project,
    project,
)

# --- the cost one run may state ---------------------------------------------------------------


def test_a_run_above_the_ceiling_is_refused_with_the_ceiling(
    client, project, flow_runs
):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project, max_cost_usd=11)

    assert is_above(resp, 10.0), shown(resp)
    assert flow_runs.calls == []
    assert runs_started(chief) == 0


def test_a_run_within_the_ceiling_passes_and_the_route_takes_the_cost(
    client, project, flow_runs
):
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project, max_cost_usd=5)

    assert resp.status_code == 200, shown(resp)
    assert [call["max_cost_usd"] for call in flow_runs.calls] == [5.0]
    assert runs_started(chief) == 1


def test_a_cost_at_the_ceiling_passes_and_a_hair_above_it_does_not(
    client, project, flow_runs
):
    chief = _chief("operator", project)

    at = start_flow(client, chief, project, max_cost_usd=10)
    above = start_flow(client, chief, project, max_cost_usd=10.000000000000002)

    assert at.status_code == 200, shown(at)
    assert is_above(above), shown(above)
    assert [call["max_cost_usd"] for call in flow_runs.calls] == [10.0]


def test_the_ceiling_is_the_setting_read_on_every_call(client, project, flow_runs):
    chief = _chief("operator", project)
    setting(CEILING_KEY, "2.5")

    refused = start_flow(client, chief, project, max_cost_usd=3)
    setting(CEILING_KEY, "4")
    allowed = start_flow(client, chief, project, max_cost_usd=3)

    assert is_above(refused, 2.5), shown(refused)
    assert allowed.status_code == 200, shown(allowed)


def test_a_retry_above_the_ceiling_is_refused_and_one_within_it_passes(
    client, project, flow_runs, finished_run
):
    chief = _chief("operator", project)
    finished_run()

    refused = retry(client, chief, project, max_cost_usd=11)
    allowed = retry(client, chief, project, max_cost_usd=5)

    assert is_above(refused), shown(refused)
    assert allowed.status_code == 200, shown(allowed)
    assert [call["max_cost_usd"] for call in flow_runs.calls] == [5.0]
    assert runs_started(chief) == 1


def test_a_flow_run_that_states_no_cost_is_judged_at_the_cost_the_route_uses(
    client, project, flow_runs
):
    """``start_run`` caps a run at $1 when no cost is given: a ceiling under that must refuse
    the call that does not state one, or it would run above the ceiling."""
    chief = _chief("operator", project)

    unstated = start_flow(client, chief, project)
    setting(CEILING_KEY, "0.5")
    refused = start_flow(client, chief, project)

    assert unstated.status_code == 200, shown(unstated)
    assert is_above(refused, 0.5), shown(refused)
    assert [call["max_cost_usd"] for call in flow_runs.calls] == [1.0]


def test_the_cost_a_flow_start_runs_at_when_it_states_none_is_start_runs_own():
    """The gate judges a start that states no cost at ``DEFAULT_FLOW_COST_USD``, the number the
    route passes ``start_run``; if ``start_run`` changed its default they would part."""
    import inspect

    from pathly_orchestrator.http_server.blueprints.control._cost import (
        DEFAULT_FLOW_COST_USD,
    )
    from pathly_orchestrator.supervisor.api import start_run

    own = inspect.signature(start_run).parameters["max_cost_usd"].default

    assert DEFAULT_FLOW_COST_USD == own


def test_a_start_that_takes_no_cost_is_not_judged_on_one(client, project, stubs):
    """A goal or a board run has no per-run cost to state: the ceiling does not apply to it."""
    chief = _chief("operator", project)
    setting(CEILING_KEY, "0.5")
    goal = project_row(project, "goal")

    resp = client.post(
        "/runs",
        json={"kind": "goal", "goal_id": goal, "project_root": str(project)},
        headers=chief.headers,
    )

    assert resp.status_code == 200, shown(resp)


# --- the runs one session may start -----------------------------------------------------------


def test_with_a_limit_of_two_the_third_start_is_refused(client, project, flow_runs):
    setting(LIMIT_KEY, "2")
    chief = _chief("operator", project)

    answers = [start_flow(client, chief, project) for _ in range(3)]

    assert [r.status_code for r in answers[:2]] == [200, 200]
    assert is_maxed(answers[2], 2), shown(answers[2])
    assert len(flow_runs.calls) == 2
    assert runs_started(chief) == 2


def test_the_default_limit_is_twenty(client, project, flow_runs):
    chief = _chief("operator", project)

    answers = [start_flow(client, chief, project) for _ in range(21)]

    assert {r.status_code for r in answers[:20]} == {200}
    assert is_maxed(answers[20], 20), shown(answers[20])


def test_a_limit_of_zero_means_no_run_may_start(client, project, flow_runs):
    setting(LIMIT_KEY, "0")
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert is_maxed(resp, 0), shown(resp)
    assert flow_runs.calls == []


def test_the_user_raises_the_limit_for_the_session_already_open(
    client, project, flow_runs
):
    setting(LIMIT_KEY, "1")
    chief = _chief("operator", project)
    first = start_flow(client, chief, project)
    second = start_flow(client, chief, project)

    setting(LIMIT_KEY, "3")
    third = start_flow(client, chief, project)

    assert first.status_code == 200 and is_maxed(second, 1)
    assert third.status_code == 200, shown(third)
    assert runs_started(chief) == 2


@pytest.mark.parametrize("name", list(STARTS))
def test_each_route_that_starts_work_counts_one(
    client, project, stubs, flow_runs, finished_run, name
):
    chief = _chief("operator", project)

    resp = STARTS[name](client, chief, project, finished_run)

    assert resp.status_code == 200, shown(resp)
    assert runs_started(chief) == 1


@pytest.mark.parametrize("name", list(STARTS))
def test_the_routes_share_one_count(
    client, project, stubs, flow_runs, finished_run, name
):
    """At a limit of one, the first start of any route uses it and every other is refused."""
    setting(LIMIT_KEY, "1")
    chief = _chief("operator", project)
    assert STARTS[name](client, chief, project, finished_run).status_code == 200

    for other, call in STARTS.items():
        resp = call(client, chief, project, finished_run)

        assert is_maxed(resp, 1), (name, other, shown(resp))


# --- a start the route refuses gives its slot back ---------------------------------------------


def test_a_start_the_route_answers_with_400_leaves_the_count_where_it_was(
    client, project, flow_runs
):
    chief = _chief("operator", project)
    body = {"kind": "flow", "flow": "team", "project_root": str(project)}

    resp = client.post("/runs", json=body, headers=chief.headers)

    assert resp.status_code == 400, shown(resp)
    assert runs_started(chief) == 0


def test_a_success_counts_and_a_later_400_does_not_take_it_back(
    client, project, flow_runs
):
    chief = _chief("operator", project)
    ok = start_flow(client, chief, project)
    bad = client.post(
        "/runs",
        json={"kind": "flow", "project_root": str(project)},
        headers=chief.headers,
    )

    assert ok.status_code == 200 and bad.status_code == 400
    assert runs_started(chief) == 1


def test_a_start_that_fails_validation_again_and_again_uses_no_slot(
    client, project, flow_runs
):
    setting(LIMIT_KEY, "2")
    chief = _chief("operator", project)
    body = {"kind": "flow", "project_root": str(project)}

    refused = [client.post("/runs", json=body, headers=chief.headers) for _ in range(6)]
    ok = start_flow(client, chief, project)

    assert {r.status_code for r in refused} == {400}
    assert ok.status_code == 200, shown(ok)
    assert runs_started(chief) == 1


def test_a_409_gives_the_slot_back(client, project, flow_runs):
    flow_runs.error = ValueError("Run for topic 'demo' is already active")
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 409, shown(resp)
    assert runs_started(chief) == 0


def test_an_unknown_goal_or_task_gives_the_slot_back(client, project):
    chief = _chief("operator", project)
    cases = [
        ("/comms/goals/run", {"goal_id": "no-such-goal"}),
        ("/comms/tasks/run", {"message_id": "no-such-task"}),
        ("/runs", {"kind": "goal", "goal_id": "no-such-goal"}),
        ("/comms/run", {}),
    ]

    for path, body in cases:
        resp = client.post(
            path, json={**body, "project_root": str(project)}, headers=chief.headers
        )

        assert 400 <= resp.status_code < 500, (path, shown(resp))
        assert runs_started(chief) == 0, path


def test_a_retry_with_no_cost_is_a_400_and_gives_the_slot_back(
    client, project, flow_runs, finished_run
):
    chief = _chief("operator", project)
    finished_run()

    resp = retry(client, chief, project)

    assert resp.status_code == 400, shown(resp)
    assert runs_started(chief) == 0


def test_a_500_keeps_the_slot(client, project, flow_runs):
    """The server cannot tell whether work started, so the slot stays used."""
    flow_runs.error = RuntimeError("the spawn failed")
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 500, shown(resp)
    assert runs_started(chief) == 1


# --- what does not count ----------------------------------------------------------------------


def test_a_decompose_call_does_not_count(client, project, stubs):
    setting(LIMIT_KEY, "0")
    chief = _chief("operator", project)
    goal = project_row(project, "goal")
    body = {"goal_id": goal, "mode": "planner", "project_root": str(project)}

    resp = client.post("/comms/goals/decompose", json=body, headers=chief.headers)

    assert resp.status_code == 200, shown(resp)
    assert runs_started(chief) == 0


@pytest.mark.parametrize(
    "path,body",
    [
        ("/comms/goals/decompose", {"mode": "planner"}),
        ("/comms/features/decompose", {"rigor": "light", "feature": "demo"}),
        ("/comms/project/decompose", {"rigor": "light"}),
    ],
)
def test_no_decompose_route_is_held_to_the_limit(client, project, stubs, path, body):
    setting(LIMIT_KEY, "0")
    chief = _chief("operator", project)

    resp = client.post(
        path, json={**body, "project_root": str(project)}, headers=chief.headers
    )

    assert not is_maxed(resp, 0), shown(resp)
    assert runs_started(chief) == 0


@pytest.mark.parametrize("verb", ["pause", "resume", "advance", "reroute"])
def test_the_run_verbs_that_start_nothing_do_not_count(client, project, verb):
    from chief_bind_support import record_run

    setting(LIMIT_KEY, "0")
    chief = _chief("operator", project)
    record_run(project, "run-ours")
    body = {"project_root": str(project), "adapter": "claude"}

    resp = client.post(f"/runs/run-ours/{verb}", json=body, headers=chief.headers)

    assert not is_maxed(resp, 0), shown(resp)
    assert runs_started(chief) == 0


def test_a_stop_does_not_count(client, project):
    from chief_bind_support import record_run

    setting(LIMIT_KEY, "0")
    chief = _chief("operator", project)
    record_run(project, "run-ours")

    for path in ("/runs/run-ours/stop", "/runs/run-ours/abort"):
        resp = client.post(path, json={}, headers=chief.headers)

        assert resp.status_code == 200, (path, shown(resp))
    assert runs_started(chief) == 0


def test_a_read_does_not_count(client, project):
    setting(LIMIT_KEY, "0")
    chief = _chief("operator", project)

    resp = client.get(
        "/runs", query_string={"project_root": str(project)}, headers=chief.headers
    )

    assert resp.status_code == 200, shown(resp)
    assert runs_started(chief) == 0


REFUSED_BY_THE_GATE = pytest.mark.parametrize(
    "tier,body_update",
    [
        ("planner", {}),
        ("operator", {"project_root": "OTHER"}),
        ("operator", {"surprise": 1}),
        ("operator", {"max_cost_usd": 11}),
        ("operator", {"kind": "goal", "goal_id": "OTHERS-GOAL"}),
    ],
    ids=[
        "no run action",
        "other project",
        "unlisted key",
        "above ceiling",
        "other goal",
    ],
)


def _refused_start(client, chief, project, other_project, body_update):
    """A ``POST /runs`` the gate refuses for the reason ``body_update`` brings in."""
    extra = dict(body_update)
    if extra.get("project_root") == "OTHER":
        extra["project_root"] = str(other_project)
    if extra.get("goal_id") == "OTHERS-GOAL":
        extra["goal_id"] = project_row(other_project, "goal")
    return start_flow(client, chief, project, **extra)


@REFUSED_BY_THE_GATE
def test_a_call_the_gate_refuses_costs_no_slot(
    client, project, other_project, flow_runs, tier, body_update
):
    chief = _chief(tier, project)

    resp = _refused_start(client, chief, project, other_project, body_update)

    assert _gated(resp), shown(resp)
    assert runs_started(chief) == 0
    assert flow_runs.calls == []


@REFUSED_BY_THE_GATE
def test_a_session_at_its_limit_is_told_the_other_reason_first(
    client, project, other_project, flow_runs, tier, body_update
):
    """The slot is taken last: a call another rule refuses never reaches the limit check, so
    the chief hears what is wrong with the call, not that the session is used up."""
    chief = _chief(tier, project)
    setting(LIMIT_KEY, "0")

    resp = _refused_start(client, chief, project, other_project, body_update)

    assert _gated(resp), shown(resp)
    assert not is_maxed(resp, 0), shown(resp)


def test_a_cost_above_the_ceiling_is_refused_as_such_at_the_limit(
    client, project, flow_runs
):
    chief = _chief("operator", project)
    setting(LIMIT_KEY, "0")

    resp = start_flow(client, chief, project, max_cost_usd=11)

    assert is_above(resp), shown(resp)


# --- who it applies to ------------------------------------------------------------------------


@pytest.mark.parametrize("who", ["builder", "nobody"])
def test_a_builder_token_and_no_token_have_no_ceiling_and_no_limit(
    client, project, flow_runs, who
):
    setting(LIMIT_KEY, "0")
    setting(CEILING_KEY, "0.5")
    chief = _chief("operator", project)
    headers = builder_headers(project) if who == "builder" else {}

    answers = [
        client.post(
            "/runs",
            json={
                "kind": "flow",
                "scope": "demo",
                "flow": "team",
                "project_root": str(project),
                "max_cost_usd": 1000,
            },
            headers=headers,
        )
        for _ in range(3)
    ]

    assert {r.status_code for r in answers} == {200}, [shown(r) for r in answers]
    assert [call["max_cost_usd"] for call in flow_runs.calls] == [1000.0] * 3
    assert runs_started(chief) == 0


def test_a_session_has_its_own_count(client, project, other_project, flow_runs):
    setting(LIMIT_KEY, "1")
    ours, theirs = _chief("operator", project), _chief("operator", other_project)

    first = start_flow(client, ours, project)
    again = start_flow(client, ours, project)
    other = start_flow(client, theirs, other_project)

    assert first.status_code == 200 and is_maxed(again, 1)
    assert other.status_code == 200, shown(other)
    assert (runs_started(ours), runs_started(theirs)) == (1, 1)


def test_a_chief_cannot_change_its_own_limit(client, project, flow_runs):
    """``PUT /db/settings/<key>`` is not a route a chief may call (ticket 08)."""
    from pathly_orchestrator.db.queries.app_settings import get_setting

    setting(LIMIT_KEY, "1")
    chief = _chief("operator", project)

    for key, value in ((LIMIT_KEY, "1000"), (CEILING_KEY, "1000")):
        resp = client.put(
            f"/db/settings/{key}", json={"value": value}, headers=chief.headers
        )

        assert _gated(resp), (key, shown(resp))
    assert get_setting(db(), LIMIT_KEY) == "1"
    assert get_setting(db(), CEILING_KEY) is None


def test_the_user_sets_the_limit_with_the_settings_route(client, project, flow_runs):
    chief = _chief("operator", project)

    put = client.put("/db/settings/" + LIMIT_KEY, json={"value": 1})
    first = start_flow(client, chief, project)
    second = start_flow(client, chief, project)

    assert put.status_code == 200, shown(put)
    assert first.status_code == 200 and is_maxed(second, 1)


# --- the count is a column of the session ----------------------------------------------------


def test_a_new_session_starts_at_zero(project):
    chief = _chief("operator", project)

    assert runs_started(chief) == 0


OLD_CHIEF_SESSIONS = (
    "CREATE TABLE chief_sessions ("
    " run_id TEXT PRIMARY KEY, project_root TEXT NOT NULL, preset TEXT, tier TEXT NOT NULL,"
    " engine TEXT NOT NULL, tab_id TEXT, cli_session_id TEXT, hook_secret_hash TEXT,"
    " settings_dir TEXT, opened_at REAL NOT NULL, closed_at REAL, close_reason TEXT)"
)


def _columns(conn) -> dict:
    return {r[1]: r for r in conn.execute("PRAGMA table_info(chief_sessions)")}


def test_the_migration_adds_the_column_to_a_database_that_has_the_table():
    from pathly_orchestrator.db.migrations_chief import add_chief_tables

    conn = sqlite3.connect(":memory:")
    conn.execute(OLD_CHIEF_SESSIONS)
    conn.execute(
        "INSERT INTO chief_sessions (run_id, project_root, tier, engine, opened_at)"
        " VALUES ('old-1', '/p', 'status', 'claude', 1.0)"
    )
    assert "runs_started" not in _columns(conn)

    add_chief_tables(conn)

    column = _columns(conn)["runs_started"]
    assert column[2] == "INTEGER" and column[3] == 1 and column[4] == "0"
    kept = conn.execute("SELECT run_id, runs_started FROM chief_sessions").fetchall()
    assert [tuple(r) for r in kept] == [("old-1", 0)]


def test_the_migration_runs_twice_on_an_old_and_on_a_new_database():
    from pathly_orchestrator.db.migrations_chief import add_chief_tables

    old, new = sqlite3.connect(":memory:"), sqlite3.connect(":memory:")
    old.execute(OLD_CHIEF_SESSIONS)

    for conn in (old, new):
        add_chief_tables(conn)
        add_chief_tables(conn)

        names = [name for name in _columns(conn)]
        assert names.count("runs_started") == 1


class _AlterFails(sqlite3.Connection):
    """A connection whose ``ALTER TABLE`` raises ``OperationalError``; ``also_adds`` first makes
    the change, as another connection that got there first would have."""

    also_adds = False

    def execute(self, sql, *args):
        if sql.startswith("ALTER TABLE"):
            if self.also_adds:
                super().execute(sql, *args)
            raise sqlite3.OperationalError("duplicate column name: runs_started")
        return super().execute(sql, *args)


def test_a_failed_alter_that_leaves_the_column_missing_is_not_swallowed():
    from pathly_orchestrator.db.migrations_chief import add_chief_tables

    conn = sqlite3.connect(":memory:", factory=_AlterFails)
    conn.execute(OLD_CHIEF_SESSIONS)

    with pytest.raises(sqlite3.OperationalError):
        add_chief_tables(conn)

    assert "runs_started" not in _columns(conn)


def test_a_column_another_connection_added_first_is_not_an_error():
    from pathly_orchestrator.db.migrations_chief import add_chief_tables

    conn = sqlite3.connect(":memory:", factory=_AlterFails)
    conn.also_adds = True
    conn.execute(OLD_CHIEF_SESSIONS)

    add_chief_tables(conn)

    assert list(_columns(conn)).count("runs_started") == 1


def test_the_additive_migrations_run_twice_on_the_live_database(project):
    from pathly_orchestrator.db.migrations_incremental import _add_additive_migrations

    chief = _chief("operator", project)
    db().execute("UPDATE chief_sessions SET runs_started = 4")
    db().commit()

    _add_additive_migrations(db())
    _add_additive_migrations(db())

    assert runs_started(chief) == 4


# --- GET /chief/session reports the counts -----------------------------------------------------


def _session(client, project):
    resp = client.get("/chief/session", query_string={"project_root": str(project)})
    assert resp.status_code == 200, shown(resp)
    return resp.get_json()


def test_the_session_reports_the_counts_and_the_limits(client, project, flow_runs):
    chief = _chief("operator", project)

    before = _session(client, project)
    start_flow(client, chief, project)
    start_flow(client, chief, project)
    setting(LIMIT_KEY, "7")
    setting(CEILING_KEY, "3.5")
    after = _session(client, project)

    assert before["open"] is True and before["run_id"] == chief.run_id
    assert (
        before["runs_started"],
        before["max_runs_per_session"],
        before["max_cost_usd_per_run"],
    ) == (0, 20, 10.0)
    assert (
        after["runs_started"],
        after["max_runs_per_session"],
        after["max_cost_usd_per_run"],
    ) == (2, 7, 3.5)


def test_a_session_that_is_not_open_reports_no_counts(client, project):
    assert _session(client, project) == {"open": False}
