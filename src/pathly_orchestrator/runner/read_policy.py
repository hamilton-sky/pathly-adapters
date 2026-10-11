"""Role read policy: one definition of the board read wall.

``policy_predicate`` compiles a policy to a SQL fragment over ``comms_messages``;
``row_allowed`` is its pure twin. They must agree (tests enforce it). Standard
library only.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, TypedDict

from ..db.queries.app_settings import _board_scope_key, get_board_scope, get_setting

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


def _copy_policy(policy: ReadPolicy) -> ReadPolicy:
    return {k: list(v) if isinstance(v, list) else v for k, v in policy.items()}


def _stored_exclusions(
    conn: sqlite3.Connection, project_root: str, feature: str, role: str
) -> dict[str, list[str]] | None:
    """exclude_* of the row ``get_board_scope`` would use, or None when no row applies."""
    for key in (
        _board_scope_key(project_root, feature, role),
        _board_scope_key(project_root, feature),
    ):
        raw = get_setting(conn, key)
        if raw is None:
            continue
        try:
            parsed = json.loads(raw)
            found = {
                k: [str(x) for x in parsed[k]]
                for k in ("exclude_types", "exclude_authors")
                if isinstance(parsed.get(k), list)
            }
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
        return found
    return None


def resolve_read_policy(
    conn: sqlite3.Connection,
    role: str | None,
    feature: str,
    project_root: str = "",
) -> ReadPolicy:
    """Per-role row -> per-feature row -> ``BUILTIN_DEFAULTS[role]`` -> allow all.

    A stored row without ``exclude_*`` keys does not fall through to the built-in wall.
    ``role=None`` (no caller identity) is the ``anonymous`` built-in. Always a fresh copy.
    """
    if role is None:
        return _copy_policy(BUILTIN_DEFAULTS["anonymous"])
    stored = _stored_exclusions(conn, project_root, feature, role)
    if stored is not None:
        policy: ReadPolicy = dict(get_board_scope(conn, project_root, feature, role))
        policy.update(stored)
        return policy
    if role in BUILTIN_DEFAULTS:
        return _copy_policy(BUILTIN_DEFAULTS[role])
    return {"feature": True, "project": True, "global": True}
