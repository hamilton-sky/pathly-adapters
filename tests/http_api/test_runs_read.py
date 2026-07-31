"""Control-plane run read API — GET /runs, GET /runs/<run_id> (unified-control-plane P0,
ARCHITECTURE §5, AC-1/AC-2).

Exercises the new /control blueprint over a Flask test client: /runs is project_root-scoped
and carries the T3 row shape + overlay capabilities; no project_root -> empty 200; limit is
capped; /runs/<id> returns 200 detail or 404; and a live 'running' registry entry upgrades
the persisted status. DB isolated per-test by conftest._isolate_db.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.fixture()
def client(tmp_path):
    """Flask test client (registers the control blueprint on import)."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def _seed_run(conn, pr, feat, run_id, *, status="done", adapter="claude", cost=0.0,
              tokens=0, started="2026-07-30T10:00:00+00:00",
              finished: "str | None" = "2026-07-30T10:05:00Z"):
    from pathly_orchestrator.db.queries.run_history import upsert_run

    upsert_run(conn, pr, feat, run_id, status, started_at=started, finished_at=finished,
               adapter=adapter, board_scope=feat)
    if cost or tokens:
        conn.execute(
            "INSERT INTO agent_invocations "
            "(project_root,feature,run_id,stage,started_at,tokens_in,tokens_out,cost_usd,board_scope) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (pr, feat, run_id, "BUILDING", started, tokens, 0, cost, feat),
        )
        conn.commit()


def test_list_runs_scoped_and_shaped(client):
    """GET /runs?project_root=… lists only that project_root's runs, each with the T3 shape
    + a capabilities hint (AC-1)."""
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    _seed_run(conn, pr, "featX", "run-here-0001", cost=0.10, tokens=1500)
    _seed_run(conn, pr + "-other", "featY", "run-there-0002", cost=0.20, tokens=999)

    body = c.get(f"/runs?project_root={pr}").get_json()
    ids = {r["run_id"] for r in body}
    assert "run-here-0001" in ids
    assert "run-there-0002" not in ids  # scoped out by project_root

    row = next(r for r in body if r["run_id"] == "run-here-0001")
    assert {"run_id", "kind", "feature", "board_scope", "status", "adapter", "started_at",
            "finished_at", "stage_count", "cost_usd", "tokens_total", "capabilities"} <= set(row)
    assert row["kind"] == "single"
    assert row["cost_usd"] == pytest.approx(0.10)
    assert row["tokens_total"] == 1500
    assert row["capabilities"] == ["abort"]


def test_list_runs_no_project_root_is_empty_200(client):
    c, _ = client
    resp = c.get("/runs")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_list_runs_limit_is_respected(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    for i in range(3):
        _seed_run(conn, pr, "featX", f"run-{i}-000{i}",
                  started=f"2026-07-30T10:0{i}:00+00:00")
    body = c.get(f"/runs?project_root={pr}&limit=1").get_json()
    assert len(body) == 1


def test_get_run_detail_200_and_shape(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    _seed_run(conn, pr, "featX", "run-detail-0007", cost=0.05, tokens=300)

    resp = c.get("/runs/run-detail-0007")
    assert resp.status_code == 200
    d = resp.get_json()
    assert set(d) == {"run", "stages", "logs", "board", "artifacts", "cost"}
    assert d["run"]["run_id"] == "run-detail-0007"
    assert d["cost"]["cost_usd"] == pytest.approx(0.05)


def test_get_run_detail_unknown_returns_404(client):
    c, _ = client
    resp = c.get("/runs/does-not-exist")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "unknown run_id"}


def test_overlay_upgrades_running_row(client, monkeypatch):
    """A persisted 'running' row is upgraded to the LIVE registry status (AC-2 overlay)."""
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.supervisor import registry as reg

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    _seed_run(conn, pr, "featX", "run-live-0009", status="running", finished=None)
    monkeypatch.setitem(
        reg._registry, "topicLive", SimpleNamespace(run_id="run-live-0009", status="paused")
    )

    body = c.get(f"/runs?project_root={pr}").get_json()
    row = next(r for r in body if r["run_id"] == "run-live-0009")
    assert row["status"] == "paused"  # upgraded from the live registry
    assert row["capabilities"] == ["abort"]
