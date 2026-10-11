"""Role read policy: one definition of what a role's board reads withhold.

Stdlib only. ``policy_predicate`` (SQL) and ``row_allowed`` (pure) encode the same rule and
must agree; tests enforce it.
"""

from __future__ import annotations

from typing import Any, Mapping, TypedDict

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
        "exclude_authors": ["builder"],
    },
}

NEVER_WITHHELD_TYPES = frozenset(
    {"decision", "constraint", "goal", "task", "escalation"}
)


def row_allowed(
    row: Mapping[str, Any], policy: Mapping[str, Any], caller_run_id: str | None
) -> bool:
    """True when ``policy`` lets the caller see ``row``."""
    types = policy.get("exclude_types") or []
    rtype = row.get("type")
    if rtype not in types or rtype in NEVER_WITHHELD_TYPES:
        return True
    own = row.get("author_run_id")
    if caller_run_id is not None and own is not None and own == caller_run_id:
        return True
    authors = policy.get("exclude_authors") or []
    if not authors:
        return False
    return not (row.get("author_role") in authors or row.get("author_source") == "none")


def policy_predicate(
    policy: Mapping[str, Any], caller_run_id: str | None
) -> tuple[str, list]:
    """SQL fragment (``?`` params) over comms_messages, same rule as ``row_allowed``."""
    types = [
        t for t in (policy.get("exclude_types") or []) if t not in NEVER_WITHHELD_TYPES
    ]
    if not types:
        return "1=1", []
    params: list = list(types)
    clauses = [f"COALESCE(type, '') IN ({','.join('?' * len(types))})"]
    if caller_run_id is not None:
        clauses.append("COALESCE(author_run_id, '') != ?")
        params.append(caller_run_id)
    authors = policy.get("exclude_authors") or []
    if authors:
        clauses.append(
            f"(COALESCE(author_role, '') IN ({','.join('?' * len(authors))})"
            " OR COALESCE(author_source, '') = 'none')"
        )
        params.extend(authors)
    return f"NOT ({' AND '.join(clauses)})", params
