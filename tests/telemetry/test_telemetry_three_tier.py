"""Tests for the three-tier telemetry feature (telemetry-three-tier).

Covers:
  T1/T3 — scope_tier is persisted on agent_invocations + otel_spans.
  T2    — project_agent_done writes ONE invocation + ONE span from an AGENT_DONE
          (the universal projector that lights up board/single/loop runs).
  T4    — goal=trace / task=span: a task span shares the goal trace and parents
          the goal root span.
  T5    — /db/rollup aggregates feature -> project -> global with no double-count.
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


# ── T2 / T1 / T3 — the universal projector ──────────────────────────────────


def test_project_agent_done_writes_tagged_invocation_and_span(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import read_agent_invocations
    from pathly_orchestrator.db.queries.otel_spans import read_otel_spans
    from pathly_orchestrator.runner.telemetry import project_agent_done

    pr, feat = str(tmp_path), "telem-feat"
    project_agent_done(
        project_root=pr,
        feature=feat,
        agent_done={
            "cost_usd": 0.25,
            "tokens_in": 80,
            "tokens_out": 40,
            "summary": "did the thing",
            "agent": "builder",
        },
        run_id="sched-x",
        stage="task",
        scope_tier="project",
        trace_id="trace-1",
        wall_seconds=2.0,
    )
    conn = get_db()
    invs = read_agent_invocations(conn, pr, feat)
    spans = read_otel_spans(conn, pr, feat)
    assert len(invs) == 1 and len(spans) == 1
    assert invs[0]["scope_tier"] == "project"
    assert invs[0]["cost_usd"] == 0.25 and invs[0]["agent_role"] == "builder"
    assert spans[0]["scope_tier"] == "project" and spans[0]["trace_id"] == "trace-1"


def test_project_agent_done_estimates_codex_cost_from_tokens(tmp_path):
    """A codex one-shot reports tokens but no dollar cost (and carries no explicit model, just the
    adapter slug). The projector must estimate the cost from tokens rather than record $0.
    """
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import read_agent_invocations
    from pathly_orchestrator.runner.telemetry import project_agent_done

    pr, feat = str(tmp_path), "codex-oneshot"
    project_agent_done(
        project_root=pr,
        feature=feat,
        agent_done={
            "cost_usd": 0,
            "tokens_in": 1200,
            "tokens_out": 340,
            "agent": "diagrammer",
        },
        run_id="diagram-x",
        stage="ai-diagram",
        scope_tier="project",
        adapter="codex",
        wall_seconds=1.0,
    )
    inv = read_agent_invocations(get_db(), pr, feat)[0]
    assert inv["cost_source"] == "estimated"
    assert inv["cost_usd"] > 0  # gpt-5 family rate applied to the reported tokens


def test_project_agent_done_marks_agy_unavailable_not_zero(tmp_path):
    """agy emits no usage telemetry at all — a token-less row is 'unavailable', not a $0 that
    reads as a free run."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import read_agent_invocations
    from pathly_orchestrator.runner.telemetry import project_agent_done

    pr, feat = str(tmp_path), "agy-oneshot"
    project_agent_done(
        project_root=pr,
        feature=feat,
        agent_done={
            "cost_usd": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "agent": "diagrammer",
        },
        run_id="diagram-y",
        stage="ai-diagram",
        scope_tier="project",
        adapter="agy",
        wall_seconds=1.0,
    )
    inv = read_agent_invocations(get_db(), pr, feat)[0]
    assert inv["cost_source"] == "unavailable"
    assert inv["cost_usd"] == 0.0


def test_scope_tier_for_maps_board_to_tier():
    from pathly_orchestrator.runner.telemetry import scope_tier_for

    assert scope_tier_for("feature") == "feature"
    assert scope_tier_for("project") == "project"
    assert scope_tier_for("global") == "global"
    assert scope_tier_for("nonsense") == "feature"
    assert scope_tier_for(None) == "feature"


# ── T4 — goal=trace / task=span ─────────────────────────────────────────────


def test_goal_root_and_task_span_share_trace(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.otel_spans import read_otel_spans
    from pathly_orchestrator.runner.telemetry import (
        new_trace_id,
        project_agent_done,
        write_goal_root_span,
    )

    pr, feat = str(tmp_path), "telem-trace"
    tid = new_trace_id()
    write_goal_root_span(
        project_root=pr,
        feature=feat,
        goal_id="G1",
        trace_id=tid,
        span_id="goalspan",
        scope_tier="feature",
        executor="loop",
    )
    project_agent_done(
        project_root=pr,
        feature=feat,
        agent_done={"cost_usd": 0.1},
        run_id="sched-t1",
        stage="task",
        scope_tier="feature",
        trace_id=tid,
        parent_span_id="goalspan",
    )
    spans = read_otel_spans(get_db(), pr, feat)
    assert len(spans) == 2
    by_name = {s["name"]: s for s in spans}
    assert by_name["goal:G1"]["parent_span_id"] is None
    task = next(s for s in spans if s["name"] == "task")
    assert task["trace_id"] == tid and task["parent_span_id"] == "goalspan"


# ── T5 — /db/rollup: aggregate-on-read, no double-count ──────────────────────


def test_db_rollup_aggregates_without_double_count(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import write_agent_invocation

    conn = get_db()
    pr_a = str(tmp_path / "proj-a").replace("\\", "/")
    pr_b = str(tmp_path / "proj-b").replace("\\", "/")

    def inv(pr, feat, tier, cost):
        write_agent_invocation(
            conn,
            pr,
            feat,
            {
                "run_id": "r",
                "stage": "task",
                "agent_role": "builder",
                "tokens_in": 10,
                "tokens_out": 5,
                "cost_usd": cost,
                "scope_tier": tier,
            },
        )

    # 3 facts under proj-a (2 feature + 1 project), 1 under proj-b (global)
    inv(pr_a, "f1", "feature", 0.10)
    inv(pr_a, "f2", "feature", 0.10)
    inv(pr_a, "proj-a", "project", 0.50)
    inv(pr_b, "global", "global", 1.00)

    r = c.get(f"/db/rollup?project_root={pr_a}&feature=f1")
    assert r.status_code == 200
    body = r.get_json()

    # project block = only proj-a's 3 rows, summed across tiers
    proj = body["project"]
    assert proj["totals"]["invocations"] == 3
    assert round(proj["totals"]["cost_usd"], 2) == 0.70
    assert proj["by_tier"]["feature"]["invocations"] == 2
    assert proj["by_tier"]["project"]["invocations"] == 1

    # global block = ALL 4 rows, exactly once (no double-count from the project mirror idea)
    g = body["global"]
    assert g["totals"]["invocations"] == 4
    assert round(g["totals"]["cost_usd"], 2) == 1.70
    # global summed across tiers equals the row count — the decisive no-duplicate check
    tier_sum = sum(v["invocations"] for v in g["by_tier"].values())
    assert tier_sum == 4
    assert {p["project_root"] for p in g["by_project"]} == {pr_a, pr_b}

    # feature block = just f1
    assert body["feature"]["totals"]["invocations"] == 1
    assert round(body["feature"]["totals"]["cost_usd"], 2) == 0.10


# ── T6 — POST /db/invocation: client-side one-shot ingestion ─────────────────


def test_post_db_invocation_writes_one_invocation_and_span(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import read_agent_invocations
    from pathly_orchestrator.db.queries.otel_spans import read_otel_spans

    pr = str(tmp_path / "proj-inv").replace("\\", "/")

    resp = c.post(
        "/db/invocation",
        json={
            "project_root": pr,
            "feature": "editor-ai",
            "scope_tier": "project",
            "label": "ai-split",
            "agent_role": "builder",
            "adapter": "claude",
            "cost_usd": 0.042,
            "tokens_in": 100,
            "tokens_out": 50,
            "summary": "split the file",
            "wall_seconds": 3.5,
        },
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    conn = get_db()
    invs = read_agent_invocations(conn, pr, "editor-ai")
    spans = read_otel_spans(conn, pr, "editor-ai")

    assert len(invs) == 1
    assert len(spans) == 1
    assert invs[0]["scope_tier"] == "project"
    assert abs(invs[0]["cost_usd"] - 0.042) < 1e-9
    assert spans[0]["scope_tier"] == "project"


def test_post_db_invocation_parses_stdout_tail_server_side(client):
    """spawn-parse-unification: the server re-parses raw stdout_tail with the ONE parser
    (parse_result) and PREFERS it over the client cost/tokens — so a claude editor one-shot whose
    client parser bailed on a truncated envelope (recorded $0) is recovered server-side.
    """
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.invocations import read_agent_invocations

    pr = str(tmp_path / "proj-oneshot").replace("\\", "/")
    # A truncated claude envelope: the opening brace + "type":"result" are gone; only the tail with
    # the modelUsage entry survives — the exact shape that recorded claude one-shots at $0.
    truncated = (
        'sonnet-4-6":{"inputTokens":29,"outputTokens":17290,"cacheReadInputTokens":1916016,'
        '"cacheCreationInputTokens":69871,"costUSD":1.2534678}},"uuid":"x"}'
    )
    resp = c.post(
        "/db/invocation",
        json={
            "project_root": pr,
            "feature": "editor-ai",
            "scope_tier": "project",
            "label": "diagram",
            "agent_role": "diagrammer",
            "adapter": "claude",
            "stdout_tail": truncated,
            # the client parsed nothing (the $0 bug) — the server must recover from stdout_tail
            "cost_usd": 0,
            "tokens_in": 0,
            "tokens_out": 0,
        },
        content_type="application/json",
    )
    assert resp.status_code == 200
    invs = read_agent_invocations(get_db(), pr, "editor-ai")
    assert len(invs) == 1
    assert abs(invs[0]["cost_usd"] - 1.2534678) < 1e-6
    assert (invs[0]["tokens_in"] + invs[0]["tokens_out"]) == (
        29 + 1916016 + 69871 + 17290
    )
