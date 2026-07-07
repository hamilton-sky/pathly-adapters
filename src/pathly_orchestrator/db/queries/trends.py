"""Query helpers for daily trend aggregates from agent_invocations."""

from __future__ import annotations

import sqlite3


def get_daily_trends(
    conn: sqlite3.Connection,
    feature: str,
    days: int = 126,
) -> list[dict]:
    """Return daily aggregate buckets for the given feature over the trailing N days.

    Returns an empty list when the feature has no rows in the time window.
    Never raises — DB errors are propagated to the caller (blueprint handles them).
    """
    rows = conn.execute(
        """
        SELECT
            strftime('%Y-%m-%d', started_at, 'localtime') AS bucket,
            COUNT(*) AS count,
            SUM(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)) AS total_tokens,
            SUM(COALESCE(tokens_in, 0)) AS input_tokens,
            SUM(COALESCE(cache_read_tokens, 0)) AS cache_read_tokens,
            SUM(COALESCE(cache_write_tokens, 0)) AS cache_write_tokens,
            SUM(CASE WHEN cost_usd > 0 THEN cost_usd ELSE 0 END) AS cost_usd_reported,
            MAX(CASE WHEN cost_usd IS NULL OR cost_usd = 0 THEN 1 ELSE 0 END) AS has_estimated_rows
        FROM agent_invocations
        WHERE feature = ?
          AND started_at >= date('now', '-' || ? || ' days')
        GROUP BY strftime('%Y-%m-%d', started_at, 'localtime')
        ORDER BY bucket ASC
        """,
        (feature, days),
    ).fetchall()
    return [dict(r) for r in rows]


def get_daily_trends_all(
    conn: sqlite3.Connection,
    days: int = 126,
    project_root: str | None = None,
) -> list[dict]:
    """Daily aggregate buckets across ALL features (optionally one project_root).

    Backs the DB-explorer overview cost chart, which has no single feature to pin to.
    Same bucket shape as :func:`get_daily_trends`. Never raises — the blueprint owns
    error handling.
    """
    where = "started_at >= date('now', '-' || ? || ' days')"
    params: list = [days]
    if project_root:
        where += " AND project_root = ?"
        params.append(project_root)
    rows = conn.execute(
        "SELECT "
        "  strftime('%Y-%m-%d', started_at, 'localtime') AS bucket, "
        "  COUNT(*) AS count, "
        "  SUM(COALESCE(tokens_in, 0) + COALESCE(tokens_out, 0)) AS total_tokens, "
        "  SUM(COALESCE(tokens_in, 0)) AS input_tokens, "
        "  SUM(COALESCE(cache_read_tokens, 0)) AS cache_read_tokens, "
        "  SUM(COALESCE(cache_write_tokens, 0)) AS cache_write_tokens, "
        "  SUM(CASE WHEN cost_usd > 0 THEN cost_usd ELSE 0 END) AS cost_usd_reported, "
        "  MAX(CASE WHEN cost_usd IS NULL OR cost_usd = 0 THEN 1 ELSE 0 END) AS has_estimated_rows "
        "FROM agent_invocations "
        f"WHERE {where} "  # nosec B608 - {where} is an internal constant; values are bound
        "GROUP BY strftime('%Y-%m-%d', started_at, 'localtime') "
        "ORDER BY bucket ASC",
        params,
    ).fetchall()
    return [dict(r) for r in rows]
