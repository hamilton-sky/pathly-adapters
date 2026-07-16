"""Executor invocations must reconcile the real CLI billing (cost/tokens) after early-advance.

The board/single/loop executors write a provisional agent_invocation at AGENT_DONE (cost=0,
tokens=0) BEFORE the CLI's cost/tokens are known — those arrive only when the PTY exits
(parse_result). `update_invocation_billing` patches the latest invocation for a run with the
real figures so the rollups reflect actual CLI cost, not zeros. And `write_agent_invocation`
must persist provider + cost_source (previously dropped → every row NULL provider / unpriced).
"""

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.invocations import (
    write_agent_invocation,
    update_invocation_billing,
    read_agent_invocations,
)


def test_update_invocation_billing_reconciles_latest_for_run():
    conn = get_db()
    pr, feat, run = "C:/x", "billing-recon-1", "run-recon-1"
    write_agent_invocation(
        conn,
        pr,
        feat,
        {
            "run_id": run,
            "stage": "task",
            "agent_role": "builder",
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0,
            "scope_tier": "feature",
            "provider": "claude",
            "cost_source": "unpriced",
        },
    )
    n = update_invocation_billing(
        conn,
        run,
        cost_usd=1.5,
        tokens_in=1200,
        tokens_out=340,
        cost_source="provider_reported",
    )
    assert n == 1
    r = [x for x in read_agent_invocations(conn, pr, feat) if x["run_id"] == run][0]
    assert abs(r["cost_usd"] - 1.5) < 1e-9
    assert r["tokens_in"] == 1200 and r["tokens_out"] == 340
    assert r["cost_source"] == "provider_reported"
    assert r["provider"] == "claude"  # preserved via COALESCE (not overwritten to NULL)


def test_write_persists_provider_and_cost_source():
    conn = get_db()
    pr, feat, run = "C:/x", "billing-recon-2", "run-recon-2"
    write_agent_invocation(
        conn,
        pr,
        feat,
        {
            "run_id": run,
            "agent_role": "builder",
            "cost_usd": 0.42,
            "tokens_in": 10,
            "tokens_out": 5,
            "provider": "codex",
            "cost_source": "provider_reported",
            "scope_tier": "project",
        },
    )
    r = [x for x in read_agent_invocations(conn, pr, feat) if x["run_id"] == run][0]
    assert r["provider"] == "codex"
    assert r["cost_source"] == "provider_reported"


def test_update_no_run_id_is_noop():
    conn = get_db()
    assert (
        update_invocation_billing(
            conn,
            "",
            cost_usd=1.0,
            tokens_in=1,
            tokens_out=1,
            cost_source="provider_reported",
        )
        == 0
    )
