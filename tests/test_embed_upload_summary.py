"""§3a — an UPLOADED .md's generated summary feeds the message's display text +
search vector (so it surfaces in the 💡 semantic channel), while agent-created
artifacts keep their thin note (summary stays catalog-only)."""

from __future__ import annotations

import json
import time
import uuid

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _stub_summarizer(monkeypatch, summary):
    import pathly_orchestrator.runner.inference as inf
    from pathly_orchestrator.runner.inference import SummaryResult

    def fake(text, *, artifact_type="md", backend=None, max_sentences=3, timeout=30):
        if artifact_type != "md":
            return SummaryResult(None, "none")
        return SummaryResult(summary, backend or "haiku")

    monkeypatch.setattr(inf, "summarize_content", fake)
    # A non-off backend so the summarize gate passes.
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_summary_backend

    set_summary_backend(get_db(), "haiku")


def _msg_text(mid):
    from pathly_orchestrator.db.connection import get_db

    row = get_db().execute(
        "SELECT text FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    return row["text"] if row else None


def test_upload_embed_summary_updates_message_and_reembeds(client, tmp_path, monkeypatch):
    SUMMARY = f"[sum-{uuid.uuid4().hex[:6]}] storage and api topics"
    _stub_summarizer(monkeypatch, SUMMARY)

    embed_calls = []
    import pathly_orchestrator.runner.embeddings as emb
    monkeypatch.setattr(emb, "embed_async", lambda mid, text: embed_calls.append((mid, text)))

    scope = f"emb-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "NOTES.md"
    md.write_text("# Notes\n## Phase 1 — storage\nSQLite + WAL.\n", encoding="utf-8")

    r = client.post("/comms/post", json={
        "feature": scope, "from": "human", "type": "artifact",
        "text": "Uploaded NOTES.md", "board": "feature", "scope": scope,
        "artifact_path": str(md).replace("\\", "/"), "artifact_type": "md",
        "embed_summary": True,
    })
    assert r.status_code == 200, r.data
    mid = json.loads(r.data)["message_id"]

    # Wait for the async summarize → embed-summary writeback.
    for _ in range(120):
        t = _msg_text(mid)
        if t and SUMMARY in t:
            break
        time.sleep(0.1)

    text = _msg_text(mid)
    assert text and SUMMARY in text, f"message text not updated to the summary: {text!r}"
    assert text.startswith("NOTES.md:"), text  # filename-prefixed, identifiable
    # The message was re-embedded with the summary-bearing text (powers 💡 search).
    assert any(SUMMARY in t for _, t in embed_calls), f"embed_async not called with summary: {embed_calls}"


def test_agent_artifact_without_flag_keeps_note(client, tmp_path, monkeypatch):
    _stub_summarizer(monkeypatch, "[sum] should-not-touch-message")
    import pathly_orchestrator.runner.embeddings as emb
    monkeypatch.setattr(emb, "embed_async", lambda *a, **k: None)

    scope = f"noemb-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Phase 1 — x\nbody\n", encoding="utf-8")

    r = client.post("/comms/post", json={
        "feature": scope, "from": "planner", "type": "artifact",
        "text": "Agent posted DOC.md", "board": "feature", "scope": scope,
        "artifact_path": str(md).replace("\\", "/"), "artifact_type": "md",
        # no embed_summary → agent artifact: summary stays catalog-only
    })
    assert r.status_code == 200, r.data
    mid = json.loads(r.data)["message_id"]

    time.sleep(2)  # let any async summarize run
    assert _msg_text(mid) == "Agent posted DOC.md"  # message text untouched
