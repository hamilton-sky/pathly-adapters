"""``max_cost_usd`` of a run start (chief-agent 15): one reading, shared by the route and the gate.

A flow run is capped by the cost its ``RunnerState`` carries (``orchestrator`` stops spawning once
``cost_usd_so_far >= max_cost_usd``). ``POST /runs`` of a flow and the ``retry`` verb are the
routes whose body can state it. A number that is not finite makes that comparison always false
(``NaN``) or never reached (``inf``), which is no cap at all, so a cost is only ever a finite
number above 0: not a boolean (``True`` is the integer 1), not a string, not ``null``.
``chief_budget`` judges a chief's cost with ``as_cost`` too, so the gate and the route cannot
disagree about what a cost is.
"""

from __future__ import annotations

import math

# What ``supervisor.api.start_run`` caps a run at when it is given no cost. ``POST /runs`` passes
# its cost on every flow start, so the cap is in this file instead of left to that default, and
# the chief gate reads the same number for a start that states none.
DEFAULT_FLOW_COST_USD = 1.0
MESSAGE = "Field 'max_cost_usd' must be a positive number"


def as_cost(value: object) -> float | None:
    """``value`` as a cost in dollars, or None when it is not a finite number above 0.

    Integers and floats only (a boolean is refused), and an integer too large for a float is
    not a cost.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except OverflowError:
        return None
    return number if 0 < number < math.inf else None


def flow_cost(body: dict) -> float:
    """The cap a ``POST /runs`` flow start runs with: the body's ``max_cost_usd``, else
    ``DEFAULT_FLOW_COST_USD``. ``ValueError`` when the key is there and is not a cost (``null``
    included), so a body never falls back to the default by accident.
    """
    if "max_cost_usd" not in body:
        return DEFAULT_FLOW_COST_USD
    cost = as_cost(body["max_cost_usd"])
    if cost is None:
        raise ValueError(MESSAGE)
    return cost
