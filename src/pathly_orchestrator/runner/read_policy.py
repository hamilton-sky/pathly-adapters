"""Role read policy: one definition of what a role's board reads withhold.

Pure rules plus one settings read (``resolve_read_policy``). ``policy_predicate`` (SQL) and ``row_allowed`` (pure) encode the same rule and
must agree; tests enforce it.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping, TypedDict

from ..db.queries.app_settings import (
    _board_scope_key,
    get_board_scope,
    get_setting,
)

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


def _stored_row(
    conn: sqlite3.Connection, project_root: str, feature: str, role: str | None
) -> dict | None:
    """First well-formed stored board_scope row: per-role, then per-feature."""
    keys = [_board_scope_key(project_root, feature, role)] if role else []
    keys.append(_board_scope_key(project_root, feature))
    for key in keys:
        raw = get_setting(conn, key)
        if raw is None:
            continue
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def resolve_read_policy(
    conn: sqlite3.Connection,
    role: str | None,
    feature: str,
    project_root: str = "",
) -> ReadPolicy:
    """Per-role row -> per-feature row -> BUILTIN_DEFAULTS[role] -> allow-all.

    A stored row without ``exclude_*`` keys is allow-all for content (it never falls through
    to the built-in wall), so existing rows read exactly what they read today.
    ``role=None`` is the anonymous caller.
    """
    row = _stored_row(conn, project_root, feature, role)
    if row is not None:
        policy: ReadPolicy = dict(get_board_scope(conn, project_root, feature, role))
        for k in ("exclude_types", "exclude_authors"):
            v = row.get(k)
            policy[k] = [str(x) for x in v] if isinstance(v, list) else []
        return policy
    builtin = BUILTIN_DEFAULTS.get("anonymous" if role is None else role, {})
    return {
        "feature": True,
        "project": True,
        "global": True,
        "exclude_types": list(builtin.get("exclude_types", [])),
        "exclude_authors": list(builtin.get("exclude_authors", [])),
    }
