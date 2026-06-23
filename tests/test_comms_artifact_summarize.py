"""Manual per-card Summarize: POST /comms/artifacts/<id>/summarize triggers an
on-demand summary with a chosen engine, reusing the async summarizer. Plus the
configurable Ollama model helper.

The summarizer/indexer run in daemon threads that touch get_db() on other threads;
left live they race the per-test DB isolation (flip the global init flag → a later
test's fresh DB skips migrations). So we stub them and assert the route *invokes*
the summarizer correctly — deterministic, no threads, no polling.
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
    """Posting an artifact normally spawns index_artifact_async (a daemon thread).
    Stub it so it can't race the per-test DB isolation. insert_artifact still runs
    synchronously in the post route, so the artifact row is created."""
    import pathly_orchestrator.runner.hydrate as hyd

    monkeypatch.setattr(hyd, "index_artifact_async", lambda *a, **k: None)


def _artifact_id_for(message_id):
    from pathly_orchestrator.db.connection import get_db

    row = get_db().execute(
        "SELECT id FROM comms_artifacts WHERE message_id=?", (message_id,)
    ).fetchone()
    return row["id"] if row else None


def _post_artifact(client, scope, md):
    r = client.post("/comms/post", json={
        "feature": scope, "from": "human", "type": "artifact",
        "text": "Added DOC.md", "board": "feature", "scope": scope,
        "artifact_path": str(md).replace("\\", "/"), "artifact_type": "md",
    })
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def test_summarize_route_invokes_summarizer(client, tmp_path, monkeypatch):
    """The route hands the chosen engine to the async summarizer with embed_summary=True
    (so a successful summary also feeds the 💡 channel, like the upload path)."""
    import pathly_orchestrator.runner.hydrate as hyd

    calls = []
    monkeypatch.setattr(
        hyd, "_schedule_resummarize_async", lambda art_id, **kw: calls.append((art_id, kw))
    )

    scope = f"sum-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Storage\nWAL.\n## API\nroutes.\n", encoding="utf-8")
    art_id = _artifact_id_for(_post_artifact(client, scope, md))
    assert art_id, "artifact row not created"

    r = client.post(f"/comms/artifacts/{art_id}/summarize", json={"engine": "ollama"})
    assert r.status_code == 202, r.data

    assert len(calls) == 1
    called_id, kw = calls[0]
    assert called_id == art_id
    assert kw.get("backend") == "ollama"
    assert kw.get("embed_summary") is True


def test_summarize_route_omitted_engine_uses_default(client, tmp_path, monkeypatch):
    import pathly_orchestrator.runner.hydrate as hyd

    calls = []
    monkeypatch.setattr(
        hyd, "_schedule_resummarize_async", lambda art_id, **kw: calls.append((art_id, kw))
    )
    scope = f"def-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## A\nbody\n", encoding="utf-8")
    art_id = _artifact_id_for(_post_artifact(client, scope, md))

    r = client.post(f"/comms/artifacts/{art_id}/summarize", json={})
    assert r.status_code == 202, r.data
    assert calls and calls[0][1].get("backend") is None  # None ⇒ global default


def test_summarize_route_rejects_off_and_cli_engines(client, tmp_path):
    scope = f"rej-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## A\nbody\n", encoding="utf-8")
    art_id = _artifact_id_for(_post_artifact(client, scope, md))

    assert client.post(f"/comms/artifacts/{art_id}/summarize", json={"engine": "minilm"}).status_code == 400
    assert client.post(f"/comms/artifacts/{art_id}/summarize", json={"engine": "claude"}).status_code == 400
    assert client.post("/comms/artifacts/does-not-exist/summarize", json={"engine": "ollama"}).status_code == 404


def test_ollama_model_setting(monkeypatch):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import (
        get_ollama_model,
        set_ollama_model,
    )

    conn = get_db()
    monkeypatch.delenv("PATHLY_OLLAMA_MODEL", raising=False)
    set_ollama_model(conn, "deepseek-r1:1.5b")
    assert get_ollama_model(conn) == "deepseek-r1:1.5b"

    with pytest.raises(ValueError):
        set_ollama_model(conn, "   ")
