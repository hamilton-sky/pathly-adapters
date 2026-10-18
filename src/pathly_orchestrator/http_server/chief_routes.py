"""Which action each route is, for the chief gate (chief-agent).

The table is data so a test can walk ``app.url_map`` against it: a route that is not listed is
refused to a chief, whatever its tier, until someone lists it here. Reads are the exception and
are not listed one by one: every GET is ``read`` except the streams and the settings dump
(``READ_REFUSED_*``), which carry spawn tokens and stored secrets.

``ROUTE_ACTIONS`` maps ``(rule, method)`` to the default action of a route. Three routes are
refined by the request: a post by its ``type``, a run-control call by its verb, and an
acknowledgement by the row it acknowledges. ``action_for`` is the one place that combines them.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Callable, Mapping

ROUTE_ACTIONS: Mapping[tuple[str, str], str] = MappingProxyType(
    {
        ("/comms/search", "POST"): "read",
        ("/code/query", "POST"): "read",
        ("/comms/post", "POST"): "post",
        ("/comms/goals/decompose", "POST"): "plan",
        ("/comms/features/decompose", "POST"): "plan",
        ("/comms/project/decompose", "POST"): "plan",
        ("/comms/acknowledge", "POST"): "decide",
        ("/comms/supersede", "POST"): "decide",
        ("/comms/directives", "POST"): "decide",
        ("/runs", "POST"): "run",
        ("/comms/goals/run", "POST"): "run",
        ("/comms/run", "POST"): "run",
        ("/comms/tasks/run", "POST"): "run",
        ("/runs/<run_id>/<action>", "POST"): "run",
        ("/runs/<run_id>/stop", "POST"): "stop",
        ("/comms/goals/stop", "POST"): "stop",
        ("/comms/run/stop", "POST"): "stop",
        ("/comms/tasks/stop", "POST"): "stop",
        ("/runner/agent-answer", "POST"): "answer",
        ("/comms/answer", "POST"): "answer",
    }
)

READ_REFUSED_PREFIXES = ("/events/",)
READ_REFUSED_RULES = frozenset({"/db/settings"})

# A post is `post` unless its type puts it higher.
POST_TYPE_ACTIONS: Mapping[str, str] = MappingProxyType(
    {
        "goal": "plan",
        "task": "plan",
        "decision": "decide",
        "constraint": "decide",
    }
)

# ``/runs/<run_id>/<action>``: a verb not listed here is an unlisted route.
RUN_VERB_ACTIONS: Mapping[str, str] = MappingProxyType(
    {
        "pause": "run",
        "resume": "run",
        "advance": "run",
        "reroute": "run",
        "retry": "run",
        "abort": "stop",
    }
)

# A route whose body names who is posting must name the chief.
POSTS_AS_CHIEF = frozenset({"/comms/post"})

IsHumanEscalation = Callable[[object], bool]


def _post_action(base, view_args, body, is_human_escalation) -> str | None:
    kind = body.get("type")
    kind = kind.strip().lower() if isinstance(kind, str) else ""
    return POST_TYPE_ACTIONS.get(kind, base)


def _verb_action(base, view_args, body, is_human_escalation) -> str | None:
    return RUN_VERB_ACTIONS.get(view_args.get("action"))


def _acknowledge_action(base, view_args, body, is_human_escalation) -> str | None:
    return "answer" if is_human_escalation(body.get("message_id")) else base


_REFINERS = MappingProxyType(
    {
        "/comms/post": _post_action,
        "/runs/<run_id>/<action>": _verb_action,
        "/comms/acknowledge": _acknowledge_action,
    }
)


def action_for(
    rule: str,
    method: str,
    view_args: Mapping,
    body: Mapping,
    is_human_escalation: IsHumanEscalation,
) -> str | None:
    """The action a call to ``rule`` is, or None when the chief may not call it at all.

    ``method`` is the request method with HEAD already read as GET. ``is_human_escalation``
    answers whether a ``message_id`` names an escalation addressed to the human (acknowledging
    one is `answer`, not `decide`).
    """
    if method == "GET":
        refused = rule.startswith(READ_REFUSED_PREFIXES) or rule in READ_REFUSED_RULES
        return None if refused else "read"
    base = ROUTE_ACTIONS.get((rule, method))
    if base is None:
        return None
    refine = _REFINERS.get(rule)
    return refine(base, view_args, body, is_human_escalation) if refine else base
