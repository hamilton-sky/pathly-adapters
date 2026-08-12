"""Tests for the state-one-authority /db/features extension (split-db-api-explorer).

GET /db/features rows carry two new fields so Studio can read them off the DB row
instead of scanning disk mirrors directly:
  - last_summary — the most recent AGENT_DONE summary, keyed by the SAME (project_root,
    feature) tuple the row is built from (so a goal-run feature keyed by its run slug
    resolves its own summary, not the board scope's)
  - flow — from the fsm_state state_json blob

Also covers the SRP split: the four per-feature detail routes moved verbatim to
db_api_feature_detail.py and must still respond on the same URLs.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client(tmp_path):
    """Flask test client. DB is isolated per-test by conftest._isolate_db."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path


def _seed_feature(conn, pr: str, feat: str, flow: str, summary: str | None):
    from pathly_orchestrator.db.queries.fsm_events import append_event
    from pathly_orchestrator.db.queries.fsm_state import write_state

    write_state(conn, pr, feat, {"current_state": "BUILDING", "flow": flow})
    if summary is not None:
        append_event(
            conn,
            pr,
            feat,
            {
                "type": "AGENT_DONE",
                "ts": "2026-07-22T10:00:00+00:00",
                "stage": "task",
                "agent_role": "builder",
                "summary": summary,
                "outcome": "success",
            },
        )


def test_db_features_rows_carry_flow_and_last_summary(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    _seed_feature(conn, pr, "feat-a", "team", "built the widget")

    rows = c.get(f"/db/features?project_root={pr}").get_json()
    row = next(r for r in rows if r["feature"] == "feat-a")
    assert row["flow"] == "team"
    assert row["last_summary"] == "built the widget"
    assert row["source"] == "db"


def test_last_summary_keyed_per_feature_goal_run_slug(client):
    """A goal-run feature (keyed by its run slug) resolves its OWN AGENT_DONE,
    never the board scope's — the (pr, feat) key must match the row's own key."""
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    # board-scope feature and a goal-run slug feature, distinct summaries
    _seed_feature(conn, pr, "planner-hierarchy", "team", "board scope summary")
    _seed_feature(conn, pr, "g3-goal-slug-run", "team-build", "goal slug summary")

    rows = c.get(f"/db/features?project_root={pr}").get_json()
    by_feat = {r["feature"]: r for r in rows}
    assert by_feat["planner-hierarchy"]["last_summary"] == "board scope summary"
    assert by_feat["g3-goal-slug-run"]["last_summary"] == "goal slug summary"
    assert by_feat["g3-goal-slug-run"]["flow"] == "team-build"


def test_feature_without_agent_done_has_empty_last_summary(client):
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    _seed_feature(conn, pr, "feat-silent", "debug", summary=None)

    rows = c.get(f"/db/features?project_root={pr}").get_json()
    row = next(r for r in rows if r["feature"] == "feat-silent")
    assert row["last_summary"] == ""
    assert row["flow"] == "debug"


def test_filesystem_fallback_covers_feature_centric_layout(client):
    """A never-run feature under pathly/features/<name>/ (STATE.json on disk, no DB
    row) must still list — this is what lets Studio drop its own disk scan."""
    c, tmp_path = client

    feat_dir = tmp_path / "proj" / "pathly" / "features" / "never-ran"
    feat_dir.mkdir(parents=True)
    (feat_dir / "STATE.json").write_text(
        json.dumps({"current": "PLANNING", "flow": "team", "updated_at": "2026-07-22"}),
        encoding="utf-8",
    )
    pr = str(tmp_path / "proj").replace("\\", "/")

    rows = c.get(f"/db/features?project_root={pr}").get_json()
    row = next(r for r in rows if r["feature"] == "never-ran")
    assert row["source"] == "filesystem"
    assert row["state"] == "PLANNING"
    assert row["flow"] == "team"
    assert row["last_summary"] == ""


def test_split_feature_detail_routes_still_serve(client):
    """The four routes extracted to db_api_feature_detail.py answer on the same URLs
    with the same shapes."""
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    pr = str(tmp_path).replace("\\", "/")
    _seed_feature(conn, pr, "feat-detail", "team", "did the thing")

    events = c.get(f"/db/features/feat-detail/events?project_root={pr}")
    assert events.status_code == 200
    body = events.get_json()
    assert isinstance(body, list) and body
    assert body[0]["event_type"] == "AGENT_DONE"
    assert body[0]["payload"]["summary"] == "did the thing"

    for sub in ("agents", "otel", "runs"):
        r = c.get(f"/db/features/feat-detail/{sub}?project_root={pr}")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)


def test_mark_done_endpoint_sets_state_done(client):
    """POST /db/features/<f>/done writes the fsm_state row (the Studio 'Mark done'
    button), so a stuck STORMING feature renders DONE from the DB path."""
    c, tmp_path = client

    pr = str(tmp_path).replace("\\", "/")
    feat_dir = tmp_path / "pathly" / "features" / "feat-md"
    feat_dir.mkdir(parents=True)
    (feat_dir / "STATE.json").write_text(
        json.dumps({"current": "STORMING", "flow": "team"}), encoding="utf-8"
    )

    r = c.post("/db/features/feat-md/done", json={"project_root": pr})
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["state"] == "DONE"
    assert body["from_state"] == "STORMING"

    rows = c.get(f"/db/features?project_root={pr}").get_json()
    row = next(x for x in rows if x["feature"] == "feat-md")
    assert row["state"] == "DONE"
    assert row["source"] == "db"


def test_mark_done_requires_project_root(client):
    """No project_root → 400, never a silent write to the wrong scope."""
    c, _ = client
    r = c.post("/db/features/whatever/done", json={})
    assert r.status_code == 400
