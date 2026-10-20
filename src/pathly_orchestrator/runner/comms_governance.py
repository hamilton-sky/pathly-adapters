"""The decisions a prompt carries as governance: the pending ones plus the standing orders.

A pending decision reaches every prompt on the boards the run reads, until the first
acknowledgement makes it ``active``. A binding decision (``binding = 1``, a standing order)
is read whatever its status until it is superseded or deleted, but only by the role it is
addressed to (or by everyone, for ``*``), and it is read from the project board (when the run
has a project root) even when the run's project tier is off: a context-budget toggle must not
mute a standing order. Retrieval only; ``comms_formatters.render_governance_lines`` renders the
result.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Set on a row by this module and read by the formatter. The stored ``binding`` column is not
# what the formatter trusts, so a row that reaches it by any other path renders as ordinary.
BINDING_MARK = "_binding"


def _standing_orders(
    conn, boards: list[str], scopes: list[str], role: str, project_scope: str
) -> list[dict]:
    """The binding decisions for *role* on the given boards and always on the project board,
    marked, de-duplicated by id, oldest first."""
    from pathly_orchestrator.db.queries.comms_directives import get_binding_decisions

    rows = get_binding_decisions(conn, boards, scopes, role)
    if project_scope:
        rows += get_binding_decisions(conn, ["project"], [project_scope], role)
    seen: set[str] = set()
    standing: list[dict] = []
    for row in sorted(rows, key=lambda r: (str(r.get("ts") or ""), str(r["id"]))):
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        row[BINDING_MARK] = True
        standing.append(row)
    return standing


def governance_decisions(
    conn,
    boards: list[str],
    scopes: list[str],
    role: str,
    project_scope: str,
) -> list[dict]:
    """Pending decisions on *boards*/*scopes*, plus the standing orders for *role*.

    A pending row with ``binding = 1`` is left out of the pending half when the binding query
    succeeded: the query answers for it, by role, so a directive addressed to the builder is
    not handed to the reviewer while it waits for its first acknowledgement. When the query
    raises, no order is served (a warning is logged) and the pending half stays as it was, so
    a pending binding row still reaches the prompt as an ordinary pending decision.
    """
    from pathly_orchestrator.db.queries.comms import get_pending_decisions

    rows: list[dict] = []
    try:
        rows = get_pending_decisions(conn, boards=boards, scopes=scopes)
    except Exception:
        logger.debug("comms_governance: pending decisions unavailable", exc_info=True)
    try:
        standing = _standing_orders(conn, boards, scopes, role, project_scope)
    except Exception:
        logger.warning("comms_governance: standing orders unavailable", exc_info=True)
        return rows
    return [d for d in rows if not d.get("binding")] + standing


def standing_orders_only(project_scope: str, role: str, stats: dict[str, int]) -> str:
    """The board block of a run whose every tier is off: only the project's standing orders.

    ``''`` when there are none, which is what such a run always got before standing orders.
    """
    if not project_scope:
        return ""
    try:
        from pathly_orchestrator.db.connection import get_db

        rows = _standing_orders(get_db(), [], [], role, project_scope)
    except Exception:
        logger.warning("comms_governance: standing orders unavailable", exc_info=True)
        return ""
    stats["governance"] = len(rows)
    if not rows:
        return ""
    from .comms_formatters import render_governance_lines

    lines = ["## Communication Board", "", *render_governance_lines(rows, [])]
    return "\n".join(lines) + "\n"
