"""run-identity: consumers pivot onto issued identity (board_scope / run_id join).

/db/rollup's feature block and /db/features/<f>/{agents,runs} match
`feature=? OR board_scope=?`, so a goal-slug run's cost is visible under BOTH its
slug and its parent feature. Legacy rows (NULL board_scope) render exactly as
before — the feature-key heuristic survives as the fallback, not a guess.
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.db.connection import get_db
from pathly_orchestrator.db.queries.fsm_events import append_event
from pathly_orchestrator.db.queries.run_history import upsert_run


@pytest.fixture()
def client(tmp_path):
    """Flask test client. DB is isolated per-test by conftest._isolate_db."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def _seed_goal_run(conn, pr: str) -> None:
    """One goal-slug AGENT_DONE (feature=slug, board_scope=parent) + one legacy row."""
    append_event(
        conn,
        pr,
        "g1-goal-slug",
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 0,
            "run_id": "sched-t1",
            "board_scope": "parent-feat",
            "cost_usd": 2.0,
            "total_tokens": 1000,
            "ts": "2026-07-22T12:00:00Z",
        },
    )
    # legacy event — no board_scope; keys by its own feature only
    append_event(
        conn,
        pr,
        "legacy-feat",
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 0,
            "cost_usd": 0.5,
            "total_tokens": 100,
            "ts": "2026-07-22T12:00:01Z",
        },
    )


def test_goal_cost_visible_under_both_identities(client):
    c, tmp_path = client
    pr = str(tmp_path)
    _seed_goal_run(get_db(), pr)

    # under the SLUG (feature key match)
    r = c.get(f"/db/rollup?feature=g1-goal-slug&project_root={pr}")
    assert r.status_code == 200
    assert r.get_json()["feature"]["totals"]["cost_usd"] == 2.0

    # under the PARENT feature (board_scope match) — the pivot
    r = c.get(f"/db/rollup?feature=parent-feat&project_root={pr}")
    assert r.status_code == 200
    assert r.get_json()["feature"]["totals"]["cost_usd"] == 2.0

    # goal detail: the parent feature's agents view surfaces the goal invocation
    r = c.get(f"/db/features/parent-feat/agents?project_root={pr}")
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 1
    assert rows[0]["run_id"] == "sched-t1"
    assert rows[0]["board_scope"] == "parent-feat"


def test_row_matching_both_predicates_counts_once(client):
    """A plain feature run (slug == board_scope) must not double-count in the union."""
    c, tmp_path = client
    pr = str(tmp_path)
    append_event(
        get_db(),
        pr,
        "plain-feat",
        {
            "type": "AGENT_DONE",
            "agent": "builder",
            "conversation": 0,
            "board_scope": "plain-feat",
            "cost_usd": 1.0,
            "total_tokens": 10,
            "ts": "2026-07-22T12:00:00Z",
        },
    )
    r = c.get(f"/db/rollup?feature=plain-feat&project_root={pr}")
    body = r.get_json()["feature"]["totals"]
    assert body["invocations"] == 1
    assert body["cost_usd"] == 1.0


def test_legacy_null_rows_render_exactly_as_today(client):
    """Legacy rows (no board_scope) keep the old feature-key behavior."""
    c, tmp_path = client
    pr = str(tmp_path)
    _seed_goal_run(get_db(), pr)

    r = c.get(f"/db/rollup?feature=legacy-feat&project_root={pr}")
    assert r.get_json()["feature"]["totals"]["cost_usd"] == 0.5

    r = c.get(f"/db/features/legacy-feat/agents?project_root={pr}")
    rows = r.get_json()
    assert len(rows) == 1
    assert rows[0]["board_scope"] is None
    # ...and the legacy feature does NOT leak into an unrelated feature's view
    r = c.get(f"/db/features/other-feat/agents?project_root={pr}")
    assert r.get_json() == []


def test_feature_runs_matches_slug_scope_and_legacy_path(client):
    """/db/features/<f>/runs: slug rows, board_scope rows, and legacy full-path rows."""
    c, tmp_path = client
    pr = str(tmp_path)
    conn = get_db()
    upsert_run(conn, pr, "g1-goal-slug", "run-new", "done", board_scope="parent-feat")
    upsert_run(conn, pr, "features/parent-feat/goals/g1-goal-slug", "run-old", "done")

    # by slug: the new row plus the legacy full-path row (basename shim)
    r = c.get(f"/db/features/g1-goal-slug/runs?project_root={pr}")
    ids = {row["run_id"] for row in r.get_json()}
    assert ids == {"run-new", "run-old"}

    # by parent feature: the board_scope row surfaces
    r = c.get(f"/db/features/parent-feat/runs?project_root={pr}")
    ids = {row["run_id"] for row in r.get_json()}
    assert "run-new" in ids
