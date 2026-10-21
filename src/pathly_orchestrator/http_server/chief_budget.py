"""The cost ceiling and the run limit of a chief session (chief-agent 15).

Nothing else bounds an operator chief: a confused or prompt-injected one could start runs in a
loop, each with a cost of its own choosing, while the person is away. Two settings, read from the
app settings on every call (``PUT /db/settings/<key>``, which a chief may not call), bound it:

* ``chief.max_cost_usd_per_run`` (default 10): the cost one run may state. It is judged on
  ``POST /runs`` and on the ``retry`` verb of ``/runs/<run_id>/<action>``, the two routes whose
  body carries ``max_cost_usd`` (the other start routes list no such key, so a chief cannot send
  one). A value that is not a finite number above 0 is refused as well (``NaN`` makes every
  comparison false, so a route would run with no cap at all). A flow start that states none runs
  at ``DEFAULT_FLOW_COST_USD``, which is judged the same way, so a ceiling below that default
  still holds. A goal, a board run and a task run have no per-run cost to state; only the count
  below bounds those.
* ``chief.max_runs_per_session`` (default 20): the calls that start work, counted per session in
  ``chief_sessions.runs_started``: ``POST /runs``, ``/comms/goals/run``, ``/comms/run``,
  ``/comms/tasks/run`` and the ``retry`` verb (``pause``, ``resume``, ``advance`` and
  ``reroute`` are also the ``run`` action and start nothing). The decompose routes (``plan``) and
  every ``stop`` do not count. A limit of 0 means no run may start.

``budget_refusal`` is the last check of the chief gate, after the action, project, id, key and
cite rules, so a call the gate itself refuses never costs a slot. It takes the slot with one
conditional ``UPDATE`` (``chief_run_slots.take_run_slot``): two calls cannot both take the last
one. It marks the request (``flask.g.chief_run_slot``) and ``refund_run_slot``, an
``after_request`` hook, gives the slot back for a response of 400 to 499: a start the route
refused (a bad body, an unknown goal, nothing ready, a busy board) started nothing and spent
nothing. A 2xx keeps the slot even if the run fails later (it may already have spent), and so
does a 5xx (the server cannot tell whether work started). The hook acts only on the request that
took a slot, once, and never takes the count below zero.

A setting that is not a usable number (text that does not parse, not finite, a ceiling at or below
0, a negative or fractional limit) falls back to the default, which is a bound too. Not here: the
chief's own token cost, and a cost summed across a session's runs (both wait for round two's
billing of the chief session).
"""

from __future__ import annotations

import logging
import math
from typing import Mapping, Sequence

from flask import g

CEILING_KEY = "chief.max_cost_usd_per_run"
LIMIT_KEY = "chief.max_runs_per_session"
DEFAULT_CEILING_USD = 10.0
DEFAULT_RUN_LIMIT = 20
# SQLite binds an integer of 64 bits; no session reaches this many runs.
MAX_COUNT = 2**62

ABOVE = "max_cost_usd above this chief's ceiling"
NOT_A_COST = "max_cost_usd must be a finite number above 0"
MAXED = "this chief session has started its maximum number of runs"

# The calls of the `run` action that start work. `/runs/<run_id>/<action>` is decided by its verb:
# `retry` starts a new run, the others act on a run that already exists.
STARTS_A_RUN = frozenset(
    {"/runs", "/comms/goals/run", "/comms/run", "/comms/tasks/run"}
)
RUN_VERB_RULE = "/runs/<run_id>/<action>"
STARTING_VERBS = frozenset({"retry"})

# A refusal: the error text and the fields to add to the gate's usual refusal body.
Refusal = tuple[str, dict]
_UNSTATED = object()


def _number_setting(conn, key: str) -> float | None:
    """The setting ``key`` read as a float, or None when it is absent or not a number. The
    result may be ``nan`` or infinite: the callers decide what they accept."""
    from pathly_orchestrator.db.queries.app_settings import get_setting

    raw = get_setting(conn, key)
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def ceiling_usd(conn) -> float:
    """The cost one run may state: the setting, else ``DEFAULT_CEILING_USD`` when it is absent,
    not a number, not finite or not above 0."""
    from .blueprints.control._cost import as_cost

    cost = as_cost(_number_setting(conn, CEILING_KEY))
    return DEFAULT_CEILING_USD if cost is None else cost


def run_limit(conn) -> int:
    """The runs a session may start: the setting, else ``DEFAULT_RUN_LIMIT`` when it is absent
    or not a whole number of 0 or more. 0 means none; a huge number is ``MAX_COUNT``."""
    number = _number_setting(conn, LIMIT_KEY)
    if number is None or not math.isfinite(number):
        return DEFAULT_RUN_LIMIT
    if number < 0 or number != int(number):
        return DEFAULT_RUN_LIMIT
    return min(int(number), MAX_COUNT)


def starts_a_run(rule: str, view_args: Mapping) -> bool:
    """Whether a call to ``rule`` starts work and so costs a slot."""
    if rule in STARTS_A_RUN:
        return True
    return rule == RUN_VERB_RULE and view_args.get("action") in STARTING_VERBS


def _stated_cost(rule: str, view_args: Mapping, body: Mapping, default: float):
    """The cost the route would run this reading of the body with, as written (``_UNSTATED`` when
    the call has none to judge). ``POST /runs`` of a flow runs at ``default`` when it states
    none; ``retry`` states its own or is a 400.
    """
    if rule == "/runs":
        if "max_cost_usd" in body:
            return body["max_cost_usd"]
        return default if body.get("kind") == "flow" else _UNSTATED
    if rule == RUN_VERB_RULE and view_args.get("action") == "retry":
        return body.get("max_cost_usd", _UNSTATED)
    return _UNSTATED


def _cost_refusal(
    conn, rule: str, view_args: Mapping, bodies: Sequence[Mapping]
) -> Refusal | None:
    from .blueprints.control._cost import DEFAULT_FLOW_COST_USD, as_cost

    ceiling = None
    for body in bodies:
        stated = _stated_cost(rule, view_args, body, DEFAULT_FLOW_COST_USD)
        if stated is _UNSTATED:
            continue
        if ceiling is None:
            ceiling = ceiling_usd(conn)
        cost = as_cost(stated)
        if cost is None:
            return NOT_A_COST, {"ceiling": ceiling}
        if cost > ceiling:
            return ABOVE, {"ceiling": ceiling}
    return None


def forget_run_slot() -> None:
    """Drop a slot marker left on ``flask.g`` by an earlier request.

    ``g`` belongs to the app context, and a request that finds one already pushed shares it, so a
    marker an earlier request left (it raised before its response) must not be taken for this
    request's. The gate calls this before it looks at the request.
    """
    g.pop("chief_run_slot", None)


def budget_refusal(
    conn,
    run_id: str,
    rule: str,
    method: str,
    view_args: Mapping,
    bodies: Sequence[Mapping],
) -> Refusal | None:
    """The refusal for a start that is over the ceiling or the limit, else None with the slot taken.

    Only a POST that starts work is judged (``starts_a_run``). The cost of every reading of the
    body is judged first (it writes nothing), then the slot is taken once for the request.
    """
    if method != "POST" or not starts_a_run(rule, view_args):
        return None
    refusal = _cost_refusal(conn, rule, view_args, bodies)
    if refusal is not None:
        return refusal

    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    limit = run_limit(conn)
    if not take_run_slot(conn, run_id, limit):
        return MAXED, {"limit": limit}
    g.chief_run_slot = run_id
    return None


def refund_run_slot(response):
    """``after_request``: give back the slot this request took when the response is a 4xx."""
    run_id = g.pop("chief_run_slot", None)
    if run_id is None or not 400 <= response.status_code < 500:
        return response
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.chief_run_slots import give_back_run_slot

    try:
        give_back_run_slot(get_db(), run_id)
    except Exception:
        # The slot stays used: a response must not turn into a 500 because it could not be undone.
        logging.getLogger("pathly.http").warning(
            "chief: could not give back a run slot of %s", run_id, exc_info=True
        )
    return response
