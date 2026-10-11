"""Pathly's recorded spend per local day per tool — the Pathly side of cost reconciliation.

Bucketed by ``strftime(started_at, 'localtime')``, the same local-date convention as
``trends.py`` and as ccusage's own daily buckets, so both sides cut days at the same instant.
The tool is the adapter slug inferred from ``provider`` (which holds a model name, or the bare
adapter slug for one-shots spawned without ``--model``).
"""

from __future__ import annotations

import sqlite3

from ..pricing import infer_provider

_ADAPTER_SLUGS = ("claude", "codex", "copilot", "antigravity", "agy", "gemini")


def _tool_of(provider: str | None) -> str:
    p = (provider or "").strip().lower()
    if p in _ADAPTER_SLUGS:
        return p
    slug = infer_provider(p)
    return slug if slug != "unknown" else "unknown"


def daily_cost_by_tool(
    conn: sqlite3.Connection,
    since: str,
    until: str,
    project_root: str | None = None,
) -> dict[str, dict[str, dict[str, float]]]:
    """``{YYYY-MM-DD: {tool: {usd, estimated_usd, rows}}}`` for the inclusive local-date range.

    ``estimated_usd`` is the part priced by ``db/pricing.py`` (``cost_source='estimated'``)
    rather than reported by the CLI — the part a reconciliation gap most likely implicates.
    """
    where = "strftime('%Y-%m-%d', started_at, 'localtime') BETWEEN ? AND ?"
    params: list = [since, until]
    if project_root:
        where += " AND project_root = ?"
        params.append(project_root)
    rows = conn.execute(
        "SELECT strftime('%Y-%m-%d', started_at, 'localtime') AS day, provider, "
        "  SUM(COALESCE(cost_usd, 0)) AS usd, "
        "  SUM(CASE WHEN cost_source = 'estimated' THEN COALESCE(cost_usd, 0) ELSE 0 END) "
        "    AS estimated_usd, "
        "  COUNT(*) AS n "
        f"FROM agent_invocations WHERE {where} "  # nosec B608 - where is built from literals
        "GROUP BY day, provider",
        params,
    ).fetchall()
    out: dict[str, dict[str, dict[str, float]]] = {}
    for day, provider, usd, est, n in rows:
        if not day:
            continue
        agg = out.setdefault(day, {}).setdefault(
            _tool_of(provider), {"usd": 0.0, "estimated_usd": 0.0, "rows": 0}
        )
        agg["usd"] += float(usd or 0)
        agg["estimated_usd"] += float(est or 0)
        agg["rows"] += int(n or 0)
    return out
