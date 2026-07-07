"""agent_invocations is a faithful projection of the AGENT_DONE event stream.

The DB-explorer roll-up + cost chart read agent_invocations, but the real per-agent
cost lives in fsm_events (AGENT_DONE, superseded by BILLING_UPDATE). These tests pin
the projector that bridges the two: one invocation row per AGENT_DONE (keyed by the
event seq), the superseding BILLING_UPDATE folded in (never summed), event-less
editor/chat rows left untouched, and the whole thing idempotent.
"""

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.fsm_events import append_event
from pathly_orchestrator.db.queries.invocations import write_agent_invocation
from pathly_orchestrator.db.queries.invocation_projection import (
    backfill_invocations_from_events,
)
from pathly_orchestrator.db.queries.trends import get_daily_trends_all

PR = "C:/proj"


def _invocations(conn, feature):
    return conn.execute(
        "SELECT source_seq, agent_role, cost_usd, tokens_in, tokens_out, cost_source "
        "FROM agent_invocations WHERE project_root=? AND feature=? ORDER BY id",
        (PR, feature),
    ).fetchall()


def _ad(agent, conv, cost, total_tokens=0, ts="2026-07-06T12:00:00Z"):
    return {
        "type": "AGENT_DONE",
        "agent": agent,
        "conversation": conv,
        "cost_usd": cost,
        "total_tokens": total_tokens,
        "ts": ts,
    }


def _billing(agent, conv, cost, tin=0, tout=0, ts="2026-07-06T12:01:00Z"):
    return {
        "type": "BILLING_UPDATE",
        "agent": agent,
        "conversation": conv,
        "cost_usd": cost,
        "tokens_in": tin,
        "tokens_out": tout,
        "total_tokens": tin + tout,
        "ts": ts,
    }


# ── live write-path hook (append_event → on_event_appended) ──────────────────────


def test_agent_done_projects_one_invocation():
    conn = get_db()
    append_event(conn, PR, "f1", _ad("builder", 1, 0.05, 8000))
    rows = _invocations(conn, "f1")
    assert len(rows) == 1
    assert abs(rows[0]["cost_usd"] - 0.05) < 1e-9
    assert rows[0]["cost_source"] == "provider_reported"
    assert rows[0]["source_seq"] is not None
    # AGENT_DONE carries only total_tokens → parked in tokens_in
    assert rows[0]["tokens_in"] == 8000


def test_billing_update_supersedes_unpriced_agent_done():
    conn = get_db()
    append_event(conn, PR, "f2", _ad("builder", 1, 0.0, 0))  # early-advance, unpriced
    append_event(conn, PR, "f2", _billing("builder", 1, 0.1234, 5000, 900))
    rows = _invocations(conn, "f2")
    assert len(rows) == 1, "billing must patch the same row, not add one"
    assert abs(rows[0]["cost_usd"] - 0.1234) < 1e-9
    assert rows[0]["tokens_in"] == 5000 and rows[0]["tokens_out"] == 900
    assert rows[0]["cost_source"] == "provider_reported"


def test_billing_wins_over_priced_agent_done_no_double_count():
    conn = get_db()
    append_event(conn, PR, "f3", _ad("builder", 1, 0.05, 8000))
    append_event(conn, PR, "f3", _billing("builder", 1, 0.08, 6000, 2000))
    rows = _invocations(conn, "f3")
    assert len(rows) == 1
    # billing supersedes (0.08), NOT summed (0.13)
    assert abs(rows[0]["cost_usd"] - 0.08) < 1e-9


def test_orphan_billing_without_agent_done_still_records():
    conn = get_db()
    # A BILLING_UPDATE with no preceding AGENT_DONE (agent never wrote completion).
    append_event(conn, PR, "f_orphan", _billing("builder", 1, 0.09, 3000, 500))
    rows = _invocations(conn, "f_orphan")
    assert len(rows) == 1, "orphan billing must still record its cost"
    assert abs(rows[0]["cost_usd"] - 0.09) < 1e-9
    assert rows[0]["tokens_in"] == 3000 and rows[0]["tokens_out"] == 500


def test_two_agents_same_conversation_two_rows():
    conn = get_db()
    append_event(conn, PR, "f4", _ad("builder", 1, 0.05, 8000))
    append_event(conn, PR, "f4", _ad("reviewer", 1, 0.03, 4000))
    rows = _invocations(conn, "f4")
    assert len(rows) == 2
    total = sum(r["cost_usd"] for r in rows)
    assert abs(total - 0.08) < 1e-9


# ── backfill (startup rebuild) ───────────────────────────────────────────────────


def test_backfill_idempotent():
    conn = get_db()
    append_event(conn, PR, "f5", _ad("builder", 1, 0.05, 8000))
    append_event(conn, PR, "f5", _ad("reviewer", 1, 0.03, 4000))
    s1 = backfill_invocations_from_events(conn)
    n1 = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM agent_invocations"
    ).fetchone()
    s2 = backfill_invocations_from_events(conn)
    n2 = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM agent_invocations"
    ).fetchone()
    assert n1[0] == n2[0]
    assert abs(n1[1] - n2[1]) < 1e-9
    assert s1["rows"] == s2["rows"]


def test_backfill_preserves_event_less_editor_chat_rows():
    conn = get_db()
    # An editor/chat one-shot: written directly, NO AGENT_DONE event, source_seq NULL.
    write_agent_invocation(
        conn,
        PR,
        "(project)",
        {
            "run_id": "editor-1",
            "agent_role": "editor",
            "cost_usd": 0.42,
            "tokens_in": 100,
            "tokens_out": 50,
            "scope_tier": "project",
            "cost_source": "provider_reported",
        },
    )
    # A real feature with events, in the same DB.
    append_event(conn, PR, "realfeat", _ad("builder", 1, 0.05, 8000))
    backfill_invocations_from_events(conn)
    editor = conn.execute(
        "SELECT cost_usd FROM agent_invocations WHERE feature='(project)'"
    ).fetchall()
    assert len(editor) == 1, "event-less editor/chat row must survive the backfill"
    assert abs(editor[0]["cost_usd"] - 0.42) < 1e-9


def test_backfill_rebuilds_after_corruption():
    conn = get_db()
    append_event(conn, PR, "f6", _ad("builder", 1, 0.05, 8000))
    # Corrupt the projected cost, then rebuild from the authoritative event stream.
    conn.execute("UPDATE agent_invocations SET cost_usd=999 WHERE feature='f6'")
    conn.commit()
    backfill_invocations_from_events(conn)
    row = conn.execute(
        "SELECT cost_usd FROM agent_invocations WHERE feature='f6'"
    ).fetchone()
    assert abs(row["cost_usd"] - 0.05) < 1e-9


# ── trends aggregate (overview cost chart) ───────────────────────────────────────


def test_trends_all_aggregates_across_features():
    conn = get_db()
    append_event(conn, PR, "fa", _ad("builder", 1, 0.05, 8000))
    append_event(conn, PR, "fb", _ad("reviewer", 1, 0.03, 4000))
    buckets = get_daily_trends_all(conn, days=365)
    assert buckets, "overview chart must return buckets when any feature has runs"
    charted = sum(b["cost_usd_reported"] for b in buckets)
    assert abs(charted - 0.08) < 1e-9
