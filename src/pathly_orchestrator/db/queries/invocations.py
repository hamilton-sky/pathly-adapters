"""Query helpers for the agent_invocations table."""

from __future__ import annotations

import sqlite3

from ..connection import _get_write_lock


def write_agent_invocation(
    conn: sqlite3.Connection,
    project_root: str,
    feature: str,
    invocation_dict: dict,
) -> int:
    """Insert an agent invocation record. Returns the new id."""
    d = invocation_dict
    with _get_write_lock(conn):
        cur = conn.execute(
            "INSERT INTO agent_invocations "
            "(project_root, feature, run_id, stage, agent_role, started_at, finished_at, "
            " tokens_in, tokens_out, cost_usd, session_id, summary, scope_tier, "
            " provider, cost_source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                project_root,
                feature,
                d.get("run_id"),
                d.get("stage"),
                d.get("agent_role"),
                d.get("started_at"),
                d.get("finished_at"),
                d.get("tokens_in"),
                d.get("tokens_out"),
                d.get("cost_usd"),
                d.get("session_id"),
                d.get("summary"),
                d.get("scope_tier") or "feature",
                d.get("provider"),
                d.get("cost_source") or "unpriced",
            ),
        )
        conn.commit()
        return cur.lastrowid or 0


def update_invocation_billing(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    cost_usd: float,
    tokens_in: int,
    tokens_out: int,
    cost_source: str,
    provider: str | None = None,
) -> int:
    """Reconcile the real CLI billing into the LATEST invocation for a run.

    The board/single/loop executors write a provisional invocation at AGENT_DONE
    (early advance) BEFORE the CLI's cost/tokens are known — those arrive only when
    the PTY exits (parse_result). This patches the most-recent invocation for
    ``run_id`` with the real figures so the rollups reflect actual CLI cost/tokens
    instead of the zeros the provisional row carried. ``provider`` is only written
    when non-None (COALESCE preserves a provider already set at insert time).

    Returns the number of rows updated (0 when run_id is empty / no match).
    """
    if not run_id:
        return 0
    with _get_write_lock(conn):
        cur = conn.execute(
            "UPDATE agent_invocations SET cost_usd=?, tokens_in=?, tokens_out=?, "
            "cost_source=?, provider=COALESCE(?, provider) "
            "WHERE id = (SELECT id FROM agent_invocations WHERE run_id=? "
            "ORDER BY id DESC LIMIT 1)",
            (cost_usd, tokens_in, tokens_out, cost_source, provider, run_id),
        )
        conn.commit()
        return cur.rowcount or 0


def read_agent_invocations(
    conn: sqlite3.Connection, project_root: str, feature: str
) -> list[dict]:
    """Return all agent invocations for *project_root*/*feature*."""
    rows = conn.execute(
        "SELECT * FROM agent_invocations WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchall()
    return [dict(r) for r in rows]
