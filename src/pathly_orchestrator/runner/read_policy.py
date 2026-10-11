"""Role read policy: one definition of the board read wall.

``policy_predicate`` compiles a policy to a SQL fragment over ``comms_messages``;
``row_allowed`` is its pure twin. They must agree (tests enforce it). Standard
library only.
"""

from __future__ import annotations

from typing import Any, TypedDict

ReadPolicy = TypedDict(
    "ReadPolicy",
    {
        "feature": bool,
        "project": bool,
        "global": bool,
        "exclude_types": list[str],
        "exclude_authors": list[str],
    },
    total=False,
)

NEVER_WITHHELD_TYPES = frozenset(
    {"decision", "constraint", "goal", "task", "escalation"}
)

_REVIEWER: ReadPolicy = {
    "exclude_types": ["discovery", "status", "nudge", "warning"],
    "exclude_authors": ["builder"],
}
_TESTER: ReadPolicy = {
    "exclude_types": ["discovery", "status", "nudge"],
    "exclude_authors": ["builder"],
}

BUILTIN_DEFAULTS: dict[str, ReadPolicy] = {
    "reviewer": _REVIEWER,
    "tester": _TESTER,
    "chief": {"exclude_types": ["status", "nudge", "discovery"]},
    "anonymous": {
        "exclude_types": sorted(
            set(_REVIEWER["exclude_types"]) | set(_TESTER["exclude_types"])
        ),
        "exclude_authors": sorted(
            set(_REVIEWER["exclude_authors"]) | set(_TESTER["exclude_authors"])
        ),
    },
}


def _withheld_types(policy: ReadPolicy) -> list[str]:
    return [
        t for t in policy.get("exclude_types") or [] if t not in NEVER_WITHHELD_TYPES
    ]


def row_allowed(
    row: dict[str, Any], policy: ReadPolicy, caller_run_id: str | None
) -> bool:
    """True when ``row`` may be shown. Reads only type and author_* columns."""
    if row.get("type") not in _withheld_types(policy):
        return True
    own = row.get("author_run_id")
    if caller_run_id and own and own == caller_run_id:
        return True
    authors = policy.get("exclude_authors") or []
    if not authors:
        return False
    if row.get("author_source") == "none":
        return False
    return row.get("author_role") not in authors


def policy_predicate(policy: ReadPolicy, caller_run_id: str | None) -> tuple[str, list]:
    """SQL twin of ``row_allowed``: a fragment to AND into a ``WHERE``, with ``?`` params."""
    types = _withheld_types(policy)
    if not types:
        return "1=1", []
    params: list = list(types)
    withheld = f"COALESCE(type, '') IN ({','.join('?' * len(types))})"
    if caller_run_id:
        withheld += " AND COALESCE(author_run_id, '') != ?"
        params.append(caller_run_id)
    authors = policy.get("exclude_authors") or []
    if authors:
        withheld += (
            f" AND (COALESCE(author_source, '') = 'none'"
            f" OR COALESCE(author_role, '') IN ({','.join('?' * len(authors))}))"
        )
        params.extend(authors)
    return f"NOT ({withheld})", params
