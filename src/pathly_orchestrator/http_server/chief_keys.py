"""Which keys a chief may send to a route, and which names among them may reach a file
(chief-agent).

``key_refusal`` applies the key list of a ``chief_fields.ROUTE_FIELDS`` entry to one request: a
body key (a query key, for a GET) the entry does not list is refused, and so is a ``flow`` or
a ``skill`` that is not one name, because the readers join those onto a packaged folder
(``fsm_ops._load_flow``, ``skills/compose_resources``) and a goal run makes a folder of its flow.
The readers ask the same predicates (``scope_names``), so the gate and a sink cannot disagree about
a spelling.

Only the top-level keys are read: the value of a listed key is opaque here (``stage_overrides``,
``options``, ``autonomy``), and the rules of the kinds that name a project, a scope or a file are
``chief_project``'s.
"""

from __future__ import annotations

from typing import Mapping

from pathly_orchestrator.scope_names import is_flow_name, is_skill_name

from .chief_field_types import FLOW, SKILL
from .chief_fields import ROUTE_FIELDS

NOT_LISTED = "is not a key a chief may send to this route"
_NAMES = {
    FLOW: (is_flow_name, "must be one flow name, not a path"),
    SKILL: (is_skill_name, "must be one packaged skill name, not a path"),
}


def _usable(value: object) -> bool:
    """A value a route takes as given: truthy, and not a blank string."""
    return bool(value) and not (isinstance(value, str) and not value.strip())


def key_refusal(rule: str, method: str, source: Mapping) -> str | None:
    """The reason a chief may not send this request's keys to ``rule``, or None.

    ``source`` is the JSON body of a POST, or the query string of a GET (a key repeated in it is
    one key). A route with no entry is ``chief_project``'s to refuse.
    """
    fields = ROUTE_FIELDS.get((rule, method))
    if fields is None:
        return None
    allowed = fields.allowed(rule)
    for key in source.keys():
        if key not in allowed:
            return f"{key!r} {NOT_LISTED}"
    for key, kind in fields.kinds().items():
        if kind in _NAMES and _usable(source.get(key)):
            is_name, message = _NAMES[kind]
            if not is_name(source.get(key)):
                return f"{key} {message}"
    return None
