"""Which project a chief's request names, for the chief gate (chief-agent).

A project is named by ``project_root`` (body or query string), by the ``scope`` of a call on the
project board (a code query's too, since it logs onto that board), and by the project-decompose
``project`` override. ``board_values`` reads those
the way the routes do, so a value the route would use is a value the gate checks. A value is
the chief's own when it is a string that ``normalise_project_root`` maps to the session's root
(forward slashes, no trailing slash); anything else, a non-string included, is not.
"""

from __future__ import annotations

from typing import Mapping

# ``/comms/project/decompose`` takes this literal as "no override".
_NO_OVERRIDE = ("", "project")


def root_values(body: Mapping, args) -> list:
    """Every ``project_root`` the call names; an absent, null or empty one is not named."""
    return [v for v in (body.get("project_root"), *args.getlist("project_root")) if v]


def board_values(rule: str, body: Mapping) -> list:
    """Every other value the route will use as a project: a project board's scope, an override."""
    named: list = []
    if body.get("board") == "project":
        scope = body.get("scope")
        if isinstance(scope, str) and scope.strip():
            named.append(scope)
        elif rule == "/comms/post" and body.get("feature"):
            # ``/comms/post`` falls back to ``feature`` for a missing or blank scope.
            named.append(body["feature"])
    if rule == "/code/query":
        # The route logs a discovery on the project board at this scope, except for a blank scope
        # or a parenthesized marker such as "(interactive)", which it leaves unlogged.
        scope = body.get("scope") or body.get("feature")
        unlogged = isinstance(scope, str) and (
            not scope.strip() or scope.strip().startswith("(")
        )
        if scope and not unlogged:
            named.append(scope)
    override = body.get("project") if rule == "/comms/project/decompose" else None
    if override:
        override = override.strip() if isinstance(override, str) else override
        if override not in _NO_OVERRIDE:
            named.append(override)
    return named


def is_own(value: object, own: str) -> bool:
    """True when ``value`` names the project whose normalised root is ``own``."""
    from pathly_orchestrator.supervisor.chief_session import normalise_project_root

    return isinstance(value, str) and normalise_project_root(value) == own
