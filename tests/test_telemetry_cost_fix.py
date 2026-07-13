"""Tests for the telemetry-cost-fix plan (FIX B + FIX C).

FIX B — GET /db/runs/<run_id>/cost: a per-flow rollup over agent_invocations, scoped
by run_id. Every row is already billing-reconciled (invocation_projection folds a
superseding BILLING_UPDATE into its anchor row), so a plain SUM is correct.

FIX C — /db/stats and /db/features must read the SAME fact table (agent_invocations)
and both honor project_root, so the header strip total always equals the sum of the
feature cards for that project, and a different project's rows never leak in.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client(tmp_path):
    """Flask test client. DB is isolated per-test by conftest._isolate_db."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


# ── FIX B — GET /db/runs/<run_id>/cost ────────────────────────────────────────────


def test_run_cost_endpoint_sums_invocations_sharing_a_run_id(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import write_agent_invocation

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    run_id = "run-cost-1"

    def inv(feat, cost, tin, tout):
        write_agent_invocation(
            conn,
            pr,
            feat,
            {
                "run_id": run_id,
                "stage": "task",
                "agent_role": "builder",
                "tokens_in": tin,
                "tokens_out": tout,
                "cost_usd": cost,
                "scope_tier": "feature",
            },
        )

    inv("f1", 0.10, 100, 50)
    inv("f2", 0.20, 200, 80)

    r = c.get(f"/db/runs/{run_id}/cost")
    assert r.status_code == 200
    body = r.get_json()
    assert body["run_id"] == run_id
    assert body["invocations"] == 2
    assert abs(body["cost_usd"] - 0.30) < 1e-9
    assert body["tokens_in"] == 300
    assert body["tokens_out"] == 130
    assert body["tokens_total"] == 430


def test_run_cost_endpoint_unknown_run_id_returns_zeros_not_404(client):
    c, _ = client
    r = c.get("/db/runs/does-not-exist/cost")
    assert r.status_code == 200
    body = r.get_json()
    assert body["invocations"] == 0
    assert body["cost_usd"] == 0.0
    assert body["tokens_total"] == 0


# ── FIX C — /db/stats & /db/features consistency across project roots ────────────


def test_stats_and_features_consistent_per_project_root(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.fsm_state import write_state
    from pathly_orchestrator.db.queries.invocations import write_agent_invocation

    conn = get_db()
    pr_a = str(tmp_path / "proj-a").replace("\\", "/")
    pr_b = str(tmp_path / "proj-b").replace("\\", "/")

    def inv(pr, feat, cost, tin, tout):
        write_state(conn, pr, feat, {"current_state": "DONE"})
        write_agent_invocation(
            conn,
            pr,
            feat,
            {
                "run_id": "r",
                "stage": "task",
                "agent_role": "builder",
                "tokens_in": tin,
                "tokens_out": tout,
                "cost_usd": cost,
                "scope_tier": "feature",
            },
        )

    inv(pr_a, "fa1", 0.10, 100, 20)
    inv(pr_a, "fa2", 0.20, 200, 40)
    inv(pr_b, "fb1", 5.00, 900, 900)

    stats = c.get(f"/db/stats?project_root={pr_a}").get_json()
    features = c.get(f"/db/features?project_root={pr_a}").get_json()

    # root B is excluded entirely
    assert {f["feature"] for f in features} == {"fa1", "fa2"}

    # header total == sum of feature cards for the SAME project_root
    assert abs(stats["total_cost_usd"] - sum(f["cost_usd"] for f in features)) < 1e-6
    assert abs(stats["total_cost_usd"] - 0.30) < 1e-6
    assert stats["total_tokens"] == sum(f["total_tokens"] for f in features)
