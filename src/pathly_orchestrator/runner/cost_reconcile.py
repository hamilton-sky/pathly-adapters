"""Cost reconciliation — Pathly's recorded spend vs ccusage's independent machine-wide total.

Pathly measures cost with parsers and a rate table it owns (``runner/output.py``,
``db/pricing.py``). Nothing checked them against an outside measurement, so a parser that
double-counts or a stale/over-high rate would drift silently. ccusage reads the same CLIs'
transcripts and prices them independently, which gives a one-sided invariant:

    Pathly's spend for (day, tool)  <=  ccusage's spend for (day, tool)

ccusage sees EVERY session on the machine — interactive work, other projects, runs Pathly never
spawned — so Pathly being lower is expected (that ratio is reported as ``coverage``). Pathly
being HIGHER than the whole machine is impossible unless Pathly is wrong: status ``overstated``.
The reverse gap cannot be diagnosed this way, which is why ``ok`` means "not overstated", not
"exact". Both sides bucket by LOCAL calendar date.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable

DEFAULT_TOLERANCE = (
    0.10  # ccusage and Pathly price at slightly different instants/rates
)
_ABS_SLACK_USD = 0.01  # never flag sub-cent rounding

# Tools ccusage actually measures (``ccusage daily`` covers claude + codex). For any other tool
# ccusage reports nothing, so the comparison is ``not_covered`` rather than a false alarm.
COVERED_TOOLS = ("claude", "codex")


def compare_day(
    pathly: dict[str, dict[str, float]],
    ccusage: dict[str, float],
    tolerance: float = DEFAULT_TOLERANCE,
) -> list[dict[str, Any]]:
    """One comparison row per tool seen on either side for a single day."""
    rows: list[dict[str, Any]] = []
    for tool in sorted(set(pathly) | set(ccusage)):
        p = pathly.get(tool, {})
        p_usd = round(float(p.get("usd", 0.0)), 6)
        c_usd = round(float(ccusage.get(tool, 0.0)), 6)
        if tool not in COVERED_TOOLS:
            status = "not_covered"
        elif p_usd > c_usd * (1 + tolerance) + _ABS_SLACK_USD:
            status = "overstated"
        else:
            status = "ok"
        rows.append(
            {
                "tool": tool,
                "pathly_usd": p_usd,
                "pathly_estimated_usd": round(float(p.get("estimated_usd", 0.0)), 6),
                "pathly_rows": int(p.get("rows", 0)),
                "ccusage_usd": c_usd,
                "coverage": round(p_usd / c_usd, 4) if c_usd > 0 else None,
                "status": status,
            }
        )
    return rows


def reconcile_costs(
    conn: Any,
    days: int = 7,
    project_root: str | None = None,
    tolerance: float = DEFAULT_TOLERANCE,
    today: date | None = None,
    ccusage_fn: (
        Callable[[date, date], dict[str, dict[str, float]] | None] | None
    ) = None,
) -> dict[str, Any]:
    """Compare the trailing ``days`` local days (inclusive of today).

    ``status``: ``unavailable`` (ccusage not installed / failed — nothing to compare against),
    ``overstated`` (at least one covered day/tool exceeds ccusage), else ``ok``.
    ``ccusage_fn``/``today`` are injection seams for tests.
    """
    from ..db.queries.cost_by_tool import daily_cost_by_tool
    from .ccusage import ccusage_daily

    until = today or date.today()
    since = until - timedelta(days=max(1, days) - 1)
    external = (ccusage_fn or ccusage_daily)(since, until)
    base: dict[str, Any] = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "project_root": project_root,
        "tolerance": tolerance,
    }
    if external is None:
        return {
            **base,
            "status": "unavailable",
            "reason": "ccusage not found or failed (install: npm i -g ccusage)",
            "days": [],
        }
    ours = daily_cost_by_tool(conn, base["since"], base["until"], project_root)
    out_days: list[dict[str, Any]] = []
    d = since
    while d <= until:
        key = d.isoformat()
        out_days.append(
            {
                "date": key,
                "tools": compare_day(
                    ours.get(key, {}), external.get(key, {}), tolerance
                ),
            }
        )
        d += timedelta(days=1)
    overstated = [
        f"{day['date']}:{row['tool']}"
        for day in out_days
        for row in day["tools"]
        if row["status"] == "overstated"
    ]
    return {
        **base,
        "status": "overstated" if overstated else "ok",
        "overstated": overstated,
        "days": out_days,
    }


def main(argv: list[str] | None = None) -> int:
    """``python -m pathly_orchestrator.runner.cost_reconcile [--days N] [--project-root P]``.
    Prints the JSON report; exits 1 only when Pathly is overstated."""
    import argparse
    import json

    from ..db.connection import get_db

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--project-root", default=None)
    ap.add_argument("--tolerance", type=float, default=DEFAULT_TOLERANCE)
    args = ap.parse_args(argv)
    report = reconcile_costs(get_db(), args.days, args.project_root, args.tolerance)
    print(json.dumps(report, indent=2))
    return 1 if report["status"] == "overstated" else 0


if __name__ == "__main__":
    raise SystemExit(main())
