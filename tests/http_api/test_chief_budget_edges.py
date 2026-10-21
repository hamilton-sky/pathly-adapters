"""chief-agent 15: the edges of the cost ceiling and the run limit.

* ``max_cost_usd`` is a number a route turns into a cap, so every value that is not a finite
  number above 0 and at most the ceiling is refused at the gate: Python's JSON parser takes
  ``NaN`` and ``Infinity``, and a comparison with ``NaN`` is false both ways (the retry route
  would then run with no cap at all); a boolean is an integer; a string, a list and ``null`` are
  not costs.
* The two settings are text, edited by hand: anything that is not a usable number falls back to
  the default, which is a bound, not an open door.
* The slot is given back for a response of 400 to 499, once, only to the request that took it,
  and never below zero; the race for the last slot is decided by one conditional UPDATE.
"""

from __future__ import annotations

import threading

import pytest
from chief_bind_support import _boards_are_free
from chief_budget_support import (
    ABOVE,
    CEILING_KEY,
    LIMIT_KEY,
    NOT_A_COST,
    finished_run,
    flow_runs,
    flow_text,
    is_above,
    is_maxed,
    post_raw,
    retry_text,
    runs_started,
    setting,
    shown,
    start_flow,
)
from chief_cite_support import db
from chief_gate_support import _chief, _gated, app, client, project

# --- a cost the gate cannot show to be a finite number in (0, ceiling] --------------------------

HOSTILE_COSTS = [
    ("NaN", NOT_A_COST),
    ("Infinity", NOT_A_COST),
    ("-Infinity", NOT_A_COST),
    ("1e999", NOT_A_COST),
    ("-1e999", NOT_A_COST),
    ("-1", NOT_A_COST),
    ("-0.0", NOT_A_COST),
    ("0", NOT_A_COST),
    ("0.0", NOT_A_COST),
    ("true", NOT_A_COST),
    ("false", NOT_A_COST),
    ("null", NOT_A_COST),
    ('"5"', NOT_A_COST),
    ('"abc"', NOT_A_COST),
    ('""', NOT_A_COST),
    ('"NaN"', NOT_A_COST),
    ("[]", NOT_A_COST),
    ("[5]", NOT_A_COST),
    ("{}", NOT_A_COST),
    ('{"usd": 5}', NOT_A_COST),
    ("1" + "0" * 400, NOT_A_COST),
    ("11", ABOVE),
    ("10.5", ABOVE),
    ("10.000000000000002", ABOVE),
    ("1e308", ABOVE),
    ("99999999999999999999999", ABOVE),
]
IDS = [text[:24] for text, _ in HOSTILE_COSTS]


def _says(resp, error: str) -> bool:
    body = resp.get_json(silent=True) or {}
    return (
        _gated(resp)
        and body.get("error") == error
        and body.get("ceiling") == 10.0
        and body.get("action") == "run"
    )


@pytest.mark.parametrize("cost,error", HOSTILE_COSTS, ids=IDS)
def test_a_run_start_with_a_cost_that_is_not_in_range_is_refused(
    client, project, flow_runs, cost, error
):
    chief = _chief("operator", project)

    resp = post_raw(client, "/runs", flow_text(project, cost), chief.headers)

    assert _says(resp, error), shown(resp)
    assert flow_runs.calls == []
    assert runs_started(chief) == 0


@pytest.mark.parametrize("cost,error", HOSTILE_COSTS, ids=IDS)
def test_a_retry_with_a_cost_that_is_not_in_range_is_refused(
    client, project, flow_runs, finished_run, cost, error
):
    chief = _chief("operator", project)
    finished_run()

    resp = post_raw(
        client, "/runs/run-own-1/retry", retry_text(project, cost), chief.headers
    )

    assert _says(resp, error), shown(resp)
    assert flow_runs.calls == []
    assert runs_started(chief) == 0


@pytest.mark.parametrize("cost", ["0.01", "1", "1.0", "9.99", "10", "10.0", "1e1"])
def test_a_cost_in_range_passes(client, project, flow_runs, finished_run, cost):
    chief = _chief("operator", project)
    finished_run()

    start = post_raw(client, "/runs", flow_text(project, cost), chief.headers)
    again = post_raw(
        client, "/runs/run-own-1/retry", retry_text(project, cost), chief.headers
    )

    assert start.status_code == 200, shown(start)
    assert again.status_code == 200, shown(again)
    assert [c["max_cost_usd"] for c in flow_runs.calls] == [float(cost)] * 2


@pytest.mark.parametrize(
    "encoding", ["utf-8-sig", "utf-16", "utf-16-le", "utf-32", "utf-32-be"]
)
@pytest.mark.parametrize("cost,error", [("NaN", NOT_A_COST), ("11", ABOVE)])
def test_a_cost_in_an_encoding_only_one_reader_understands_is_judged_too(
    client, project, flow_runs, encoding, cost, error
):
    """The routes read ``/runs`` with ``get_json``, which understands a BOM and UTF-16/32."""
    chief = _chief("operator", project)

    resp = client.post(
        "/runs",
        data=flow_text(project, cost).encode(encoding),
        content_type="application/json",
        headers=chief.headers,
    )

    assert _says(resp, error), shown(resp)
    assert flow_runs.calls == [] and runs_started(chief) == 0


def test_the_cost_is_not_a_boolean_even_though_true_is_one(client, project, flow_runs):
    chief = _chief("operator", project)
    setting(CEILING_KEY, "0.5")

    resp = start_flow(client, chief, project, max_cost_usd=True)

    assert _gated(resp) and resp.get_json()["error"] == NOT_A_COST, shown(resp)


@pytest.mark.parametrize("path", ["/comms/goals/run", "/comms/run", "/comms/tasks/run"])
def test_the_other_start_routes_do_not_take_a_cost_at_all(client, project, path):
    chief = _chief("operator", project)
    body = {"project_root": str(project), "max_cost_usd": 1}

    resp = client.post(path, json=body, headers=chief.headers)

    assert _gated(resp) and "max_cost_usd" in resp.get_json()["error"], shown(resp)
    assert runs_started(chief) == 0


# --- the route itself: `POST /runs` takes the cost for anyone who sends it -----------------------


@pytest.mark.parametrize(
    "cost",
    ["NaN", "Infinity", "-Infinity", "0", "-1", "true", "null", '"5"', "[]", "{}"],
)
def test_the_run_route_refuses_a_cost_that_is_no_number_whoever_asks(
    client, project, flow_runs, cost
):
    """No token: the route is the only check. A cap that is ``NaN`` is never reached."""
    resp = post_raw(client, "/runs", flow_text(project, cost), {})

    assert resp.status_code == 400, shown(resp)
    assert "max_cost_usd" in resp.get_json()["error"]
    assert flow_runs.calls == []


def test_the_run_route_takes_a_cost_from_anyone_and_defaults_to_one_dollar(
    client, project, flow_runs
):
    stated = post_raw(client, "/runs", flow_text(project, "250"), {})
    unstated = client.post("/runs", json=_flow_body(project))

    assert stated.status_code == 200 and unstated.status_code == 200
    assert [call["max_cost_usd"] for call in flow_runs.calls] == [250.0, 1.0]


# --- the settings are text a person typed -----------------------------------------------------

CEILINGS = [
    ("2.5", 2.5),
    ("10", 10.0),
    (" 3 ", 3.0),
    ("1e1", 10.0),
    ("0.01", 0.01),
    ("1_0", 10.0),
    ("abc", 10.0),
    ("", 10.0),
    (" ", 10.0),
    ("0", 10.0),
    ("0.0", 10.0),
    ("-1", 10.0),
    ("-0.5", 10.0),
    ("nan", 10.0),
    ("NaN", 10.0),
    ("inf", 10.0),
    ("-inf", 10.0),
    ("Infinity", 10.0),
    ("1e999", 10.0),
    ("True", 10.0),
    ("0x10", 10.0),
    ("1,5", 10.0),
    ("$5", 10.0),
    ("5\x00", 10.0),
]


@pytest.mark.parametrize("text,expected", CEILINGS, ids=[repr(t) for t, _ in CEILINGS])
def test_the_ceiling_setting_is_read_defensively(text, expected):
    from pathly_orchestrator.http_server.chief_budget import ceiling_usd

    setting(CEILING_KEY, text)

    assert ceiling_usd(db()) == expected


def test_an_absent_ceiling_is_ten_dollars():
    from pathly_orchestrator.http_server.chief_budget import ceiling_usd

    assert ceiling_usd(db()) == 10.0


@pytest.mark.parametrize(
    "text", [t for t, expected in CEILINGS if expected == 10.0 and t != "10"]
)
def test_a_ceiling_setting_that_is_no_usable_number_leaves_the_default(
    client, project, flow_runs, text
):
    chief = _chief("operator", project)
    setting(CEILING_KEY, text)

    above = start_flow(client, chief, project, max_cost_usd=11)
    within = start_flow(client, chief, project, max_cost_usd=5)

    assert is_above(above, 10.0), shown(above)
    assert within.status_code == 200, shown(within)


LIMITS = [
    ("5", 5),
    (" 7 ", 7),
    ("5.0", 5),
    ("1e1", 10),
    ("0", 0),
    ("0.0", 0),
    ("-0", 0),
    ("-1", 20),
    ("-0.5", 20),
    ("2.5", 20),
    ("abc", 20),
    ("", 20),
    (" ", 20),
    ("nan", 20),
    ("inf", 20),
    ("-inf", 20),
    ("1e999", 20),
    ("True", 20),
    ("0x10", 20),
    ("1,000", 20),
    ("5\x00", 20),
    ("99999999999999999999", 2**62),
    ("1e30", 2**62),
]


@pytest.mark.parametrize("text,expected", LIMITS, ids=[repr(t) for t, _ in LIMITS])
def test_the_limit_setting_is_read_defensively(text, expected):
    from pathly_orchestrator.http_server.chief_budget import run_limit

    setting(LIMIT_KEY, text)

    assert run_limit(db()) == expected


def test_an_absent_limit_is_twenty():
    from pathly_orchestrator.http_server.chief_budget import run_limit

    assert run_limit(db()) == 20


def test_a_limit_nobody_could_reach_does_not_overflow_the_database(
    client, project, flow_runs
):
    setting(LIMIT_KEY, "1e30")
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 200, shown(resp)
    assert runs_started(chief) == 1


def test_a_limit_setting_that_is_no_count_leaves_the_default(
    client, project, flow_runs
):
    setting(LIMIT_KEY, "-3")
    chief = _chief("operator", project)

    answers = [start_flow(client, chief, project) for _ in range(21)]

    assert {r.status_code for r in answers[:20]} == {200}
    assert is_maxed(answers[20], 20), shown(answers[20])


# --- the slot goes back for a 4xx, once, and only to the request that took it -------------------


@pytest.fixture()
def answer_with(app, monkeypatch):
    """Make ``POST /runs`` answer with a chosen status once the gate has let the call through."""
    endpoint = next(
        r.endpoint
        for r in app.url_map.iter_rules()
        if r.rule == "/runs" and "POST" in r.methods
    )

    def use(status: int) -> None:
        monkeypatch.setitem(app.view_functions, endpoint, lambda: ("answer", status))

    return use


KEPT = [200, 201, 202, 204, 301, 302, 304, 399, 500, 501, 502, 503, 504, 599]
GIVEN_BACK = [400, 401, 403, 404, 405, 409, 410, 413, 415, 422, 429, 499]


@pytest.mark.parametrize("status", KEPT)
def test_a_response_outside_400_to_499_keeps_the_slot(
    client, project, answer_with, status
):
    chief = _chief("operator", project)
    answer_with(status)

    resp = start_flow(client, chief, project)

    assert resp.status_code == status
    assert runs_started(chief) == 1


@pytest.mark.parametrize("status", GIVEN_BACK)
def test_a_response_from_400_to_499_gives_the_slot_back(
    client, project, answer_with, status
):
    chief = _chief("operator", project)
    answer_with(status)

    resp = start_flow(client, chief, project)

    assert resp.status_code == status
    assert runs_started(chief) == 0


def test_a_view_that_raises_keeps_the_slot(app, client, project, monkeypatch):
    endpoint = next(
        r.endpoint
        for r in app.url_map.iter_rules()
        if r.rule == "/runs" and "POST" in r.methods
    )

    def boom():
        raise RuntimeError("the route fell over")

    monkeypatch.setitem(app.view_functions, endpoint, boom)
    monkeypatch.setitem(app.config, "TESTING", False)
    monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 500
    assert runs_started(chief) == 1


def test_a_4xx_from_a_hook_that_runs_after_the_gate_gives_the_slot_back(
    app, client, project, flow_runs, monkeypatch
):
    def late_hook():
        return ("slow down", 429)

    monkeypatch.setitem(
        app.before_request_funcs, None, [*app.before_request_funcs[None], late_hook]
    )
    chief = _chief("operator", project)

    resp = start_flow(client, chief, project)

    assert resp.status_code == 429
    assert flow_runs.calls == []
    assert runs_started(chief) == 0


def _set_count(chief, count: int) -> None:
    db().execute(
        "UPDATE chief_sessions SET runs_started = ? WHERE run_id = ?",
        (count, chief.run_id),
    )
    db().commit()


def _refund(app, chief, status: int, *, took_slot: bool = True, times: int = 1) -> None:
    from flask import g
    from werkzeug.wrappers import Response

    from pathly_orchestrator.http_server.chief_budget import refund_run_slot

    with app.test_request_context("/runs", method="POST"):
        if took_slot:
            g.chief_run_slot = chief.run_id
        for _ in range(times):
            refund_run_slot(Response("x", status=status))


def test_the_slot_is_given_back_once_for_one_request(app, project):
    chief = _chief("operator", project)
    _set_count(chief, 3)

    _refund(app, chief, 400, times=3)

    assert runs_started(chief) == 2


def test_the_count_never_goes_below_zero(app, project):
    chief = _chief("operator", project)

    _refund(app, chief, 400)
    _refund(app, chief, 404)

    assert runs_started(chief) == 0


def test_a_request_that_took_no_slot_gives_none_back(app, client, project, flow_runs):
    chief = _chief("operator", project)
    start_flow(client, chief, project)

    _refund(app, chief, 400, took_slot=False)
    plain = client.post("/comms/goals/decompose", json={}, headers=chief.headers)
    read = client.get("/runs/not-a-run", headers=chief.headers)

    assert plain.status_code >= 400 and read.status_code >= 400
    assert runs_started(chief) == 1


def test_a_marker_left_in_the_context_is_not_this_requests(app, client, project):
    """Under an outer app context ``g`` is shared by requests: a marker an earlier request left
    behind must not give a slot back for this one."""
    from flask import g

    chief = _chief("operator", project)
    _set_count(chief, 3)

    with app.app_context():
        g.chief_run_slot = chief.run_id
        resp = client.post("/runs", json={})

    assert resp.status_code == 400
    assert runs_started(chief) == 3


# --- two requests cannot both take the last slot ------------------------------------------------


def _fire(app, chief, project, bodies: list[dict]) -> list:
    """Send every body at once from its own thread; returns the responses in order."""
    gate = threading.Barrier(len(bodies))
    answers: list = [None] * len(bodies)
    errors: list[BaseException] = []

    def go(index: int) -> None:
        try:
            with app.test_client() as c:
                gate.wait(timeout=10)
                answers[index] = c.post(
                    "/runs", json=bodies[index], headers=chief.headers
                )
        except BaseException as exc:  # reported on the test's thread below
            errors.append(exc)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(len(bodies))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    assert errors == []
    assert all(a is not None for a in answers)
    return answers


def _flow_body(project, **extra) -> dict:
    return {
        "kind": "flow",
        "scope": "demo",
        "flow": "team",
        "project_root": str(project),
        **extra,
    }


def test_threads_racing_for_the_last_slots_get_exactly_the_limit(
    app, project, flow_runs
):
    for _ in range(4):
        setting(LIMIT_KEY, "3")
        chief = _chief("operator", project)
        before = len(flow_runs.calls)

        answers = _fire(app, chief, project, [_flow_body(project)] * 10)

        passed = [a for a in answers if a.status_code == 200]
        refused = [a for a in answers if a.status_code == 403]
        assert len(passed) == 3 and len(refused) == 7, [a.status_code for a in answers]
        assert all(is_maxed(a, 3) for a in refused)
        assert len(flow_runs.calls) - before == 3
        assert runs_started(chief) == 3


def test_threads_whose_starts_fail_leave_the_count_at_zero(app, project, flow_runs):
    setting(LIMIT_KEY, "3")
    chief = _chief("operator", project)
    bad = {"kind": "flow", "flow": "team", "project_root": str(project)}

    answers = _fire(app, chief, project, [bad] * 12)

    assert {a.status_code for a in answers} <= {400, 403}
    assert runs_started(chief) == 0


def test_threads_mixing_good_and_failing_starts_keep_the_count_true(
    app, project, flow_runs
):
    setting(LIMIT_KEY, "4")
    chief = _chief("operator", project)
    bad = {"kind": "flow", "flow": "team", "project_root": str(project)}
    bodies = [_flow_body(project) if i % 2 else bad for i in range(16)]

    answers = _fire(app, chief, project, bodies)

    started = sum(1 for a in answers if a.status_code == 200)
    assert started <= 4
    assert len(flow_runs.calls) == started
    assert runs_started(chief) == started


# --- a new route that starts work has to be decided here ----------------------------------------


def test_every_route_of_the_run_action_is_counted_or_decided_by_its_verb():
    from pathly_orchestrator.http_server.chief_budget import (
        STARTING_VERBS,
        STARTS_A_RUN,
    )
    from pathly_orchestrator.http_server.chief_routes import (
        ROUTE_ACTIONS,
        RUN_VERB_ACTIONS,
    )

    run_rules = {rule for (rule, _), action in ROUTE_ACTIONS.items() if action == "run"}
    run_verbs = {verb for verb, action in RUN_VERB_ACTIONS.items() if action == "run"}

    assert run_rules == STARTS_A_RUN | {"/runs/<run_id>/<action>"}
    assert STARTS_A_RUN == {
        "/runs",
        "/comms/goals/run",
        "/comms/run",
        "/comms/tasks/run",
    }
    assert run_verbs == {"pause", "resume", "advance", "reroute", "retry"}
    assert STARTING_VERBS == {"retry"}
