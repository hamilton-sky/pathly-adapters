"""Conv 3 (unified-ai-routing): CLIENT writes its computed summary + per-artifact
AI target back via POST /comms/artifacts/<id>/summary and /selection, plus the
app-default selection routes and the summary_selection migration column.

Mirrors test_comms_artifact_summarize.py: stub the index daemon so it can't race
the per-test DB isolation, then assert the routes persist what the client sends.
"""

from __future__ import annotations

import json
import uuid

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def _no_index_daemon(monkeypatch):
    """Stub index_artifact_async (daemon thread) so it can't race DB isolation.
    insert_artifact still runs synchronously in the post route."""
    import pathly_orchestrator.runner.hydrate as hyd

    monkeypatch.setattr(hyd, "index_artifact_async", lambda *a, **k: None)


def _artifact_id_for(message_id):
    from pathly_orchestrator.db.connection import get_db

    row = (
        get_db()
        .execute("SELECT id FROM comms_artifacts WHERE message_id=?", (message_id,))
        .fetchone()
    )
    return row["id"] if row else None


def _summary_row(artifact_id):
    from pathly_orchestrator.db.connection import get_db

    return (
        get_db()
        .execute(
            "SELECT summary, summary_selection FROM comms_artifacts WHERE id=?",
            (artifact_id,),
        )
        .fetchone()
    )


def _post_artifact(client, scope, md):
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "human",
            "type": "artifact",
            "text": "Added DOC.md",
            "board": "feature",
            "scope": scope,
            "artifact_path": str(md).replace("\\", "/"),
            "artifact_type": "md",
        },
    )
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _make_artifact(client, tmp_path):
    scope = f"sum-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Storage\nWAL.\n## API\nroutes.\n", encoding="utf-8")
    art_id = _artifact_id_for(_post_artifact(client, scope, md))
    assert art_id, "artifact row not created"
    return art_id


# ── migration ────────────────────────────────────────────────────────────


def test_summary_selection_column_exists(client, tmp_path):
    """The additive migration added comms_artifacts.summary_selection idempotently."""
    from pathly_orchestrator.db.connection import get_db

    cols = {
        r[1] for r in get_db().execute("PRAGMA table_info(comms_artifacts)").fetchall()
    }
    assert "summary_selection" in cols


# ── POST /comms/artifacts/<id>/summary ───────────────────────────────────


def test_summary_writeback_persists_text(client, tmp_path):
    art_id = _make_artifact(client, tmp_path)
    r = client.post(
        f"/comms/artifacts/{art_id}/summary",
        json={"summary": "Topic map:\n- Storage\n- API"},
    )
    assert r.status_code == 200, r.data
    row = _summary_row(art_id)
    assert row["summary"] == "Topic map:\n- Storage\n- API"
    # No selection sent ⇒ summary_selection stays NULL.
    assert row["summary_selection"] is None


def test_summary_writeback_persists_selection_when_given(client, tmp_path):
    art_id = _make_artifact(client, tmp_path)
    r = client.post(
        f"/comms/artifacts/{art_id}/summary",
        json={
            "summary": "done",
            "selection": {"type": "model", "id": "phi-4-mini"},
        },
    )
    assert r.status_code == 200, r.data
    row = _summary_row(art_id)
    assert row["summary"] == "done"
    assert json.loads(row["summary_selection"]) == {
        "type": "model",
        "id": "phi-4-mini",
    }


def test_summary_writeback_rejects_non_string_summary(client, tmp_path):
    art_id = _make_artifact(client, tmp_path)
    r = client.post(f"/comms/artifacts/{art_id}/summary", json={"summary": 5})
    assert r.status_code == 400


def test_summary_writeback_rejects_bad_selection(client, tmp_path):
    art_id = _make_artifact(client, tmp_path)
    r = client.post(
        f"/comms/artifacts/{art_id}/summary",
        json={"summary": "x", "selection": {"type": "bogus", "id": "y"}},
    )
    assert r.status_code == 400


def test_summary_writeback_404_for_unknown_artifact(client):
    r = client.post("/comms/artifacts/does-not-exist/summary", json={"summary": "x"})
    assert r.status_code == 404


# ── POST /comms/artifacts/<id>/selection ─────────────────────────────────


def test_selection_writeback_persists(client, tmp_path):
    art_id = _make_artifact(client, tmp_path)
    r = client.post(
        f"/comms/artifacts/{art_id}/selection",
        json={"selection": {"type": "engine", "id": "claude"}},
    )
    assert r.status_code == 200, r.data
    row = _summary_row(art_id)
    assert json.loads(row["summary_selection"]) == {"type": "engine", "id": "claude"}
    # Selection-only write must not touch the summary.
    assert row["summary"] in (None, "Added DOC.md")


def test_selection_writeback_rejects_missing_selection(client, tmp_path):
    art_id = _make_artifact(client, tmp_path)
    r = client.post(f"/comms/artifacts/{art_id}/selection", json={})
    assert r.status_code == 400


def test_selection_writeback_404_for_unknown_artifact(client):
    r = client.post(
        "/comms/artifacts/nope/selection",
        json={"selection": {"type": "model", "id": "x"}},
    )
    assert r.status_code == 404


# ── app-default selection (GET/POST /comms/default-selection) ─────────────


def test_default_selection_roundtrip(client):
    g0 = client.get("/comms/default-selection")
    assert g0.status_code == 200, g0.data
    # Default is unset (null) on a fresh DB.
    assert json.loads(g0.data)["selection"] is None

    r = client.post(
        "/comms/default-selection",
        json={"selection": {"type": "model", "id": "phi-4-mini"}},
    )
    assert r.status_code == 200, r.data

    g1 = client.get("/comms/default-selection")
    assert json.loads(g1.data)["selection"] == {"type": "model", "id": "phi-4-mini"}


def test_default_selection_rejects_malformed(client):
    assert (
        client.post(
            "/comms/default-selection", json={"selection": {"type": "x", "id": "y"}}
        ).status_code
        == 400
    )
    assert (
        client.post("/comms/default-selection", json={"selection": "nope"}).status_code
        == 400
    )
