"""unified-ai-routing Conv 4: server-initiated summary handoff.

On an artifact post the server runs NO inference. Instead it emits a
`summary_request` event over the comms SSE carrying the server-resolved AI target;
the Studio renderer runs aiRouter and writes the summary back. These tests assert:

- a non-minilm artifact post WITH a resolved app-default selection emits exactly one
  `summary_request` SSE event (spied on _broadcast_comms);
- `summary_backend='minilm'` (the Conv-3 client-drop path) emits NO summary_request;
- with no selection resolved (no per-artifact target, no app default), nothing is
  emitted (filename-only best-effort).

The in-process inference summarizer was removed in Conv 5, so "the server ran no
inference" is now a structural guarantee — there is nothing left to stub.

The index daemon is stubbed so it can't race per-test DB isolation; insert_artifact
still runs synchronously in the post route, so the artifact row exists.
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
    """Stub the section-index daemon (it spawns a thread that touches get_db on
    another thread, racing the per-test DB isolation). insert_artifact + the
    summary_request emit still run synchronously in the post route."""
    import pathly_orchestrator.runner.hydrate as hyd

    monkeypatch.setattr(hyd, "index_artifact_async", lambda *a, **k: None)


@pytest.fixture()
def spy(monkeypatch):
    """Spy on the comms SSE broadcast (as imported into messages.py).

    The post route builds broadcast_fn = lambda _p: _broadcast_comms(scope, _p),
    which resolves messages._broadcast_comms at call time — so patching the name in
    messages captures BOTH the message-posted COMMS_UPDATE and the summary_request
    emit that _summary_request.emit_summary_request fires through broadcast_fn."""
    import pathly_orchestrator.http_server.blueprints.comms.messages as messages

    events: list[dict] = []

    def _record(scope, payload):
        events.append(payload)

    monkeypatch.setattr(messages, "_broadcast_comms", _record)
    return events


def _set_default_selection(selection):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import (
        set_default_summary_selection,
    )

    set_default_summary_selection(get_db(), selection)


def _post_artifact(client, scope, md, *, summary_backend=None):
    body = {
        "feature": scope,
        "from": "human",
        "type": "artifact",
        "text": "Added DOC.md",
        "board": "feature",
        "scope": scope,
        "artifact_path": str(md).replace("\\", "/"),
        "artifact_type": "md",
    }
    if summary_backend is not None:
        body["summary_backend"] = summary_backend
    r = client.post("/comms/post", json=body)
    assert r.status_code == 200, r.data
    return json.loads(r.data)["message_id"]


def _summary_requests(events):
    return [e for e in events if e.get("event") == "summary_request"]


def test_artifact_post_emits_summary_request_and_no_inference(client, tmp_path, spy):
    events = spy
    _set_default_selection({"type": "model", "id": "phi-4-mini"})

    scope = f"sse-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Storage\nWAL.\n", encoding="utf-8")
    _post_artifact(client, scope, md)

    reqs = _summary_requests(events)
    assert len(reqs) == 1, f"expected one summary_request, got {events}"
    evt = reqs[0]
    assert evt["type"] == "COMMS_UPDATE"
    assert evt["scope"] == scope
    assert evt["artifact_path"].endswith("DOC.md")
    assert isinstance(evt.get("artifact_id"), str) and evt["artifact_id"]
    assert evt["selection"] == {"type": "model", "id": "phi-4-mini"}


def test_minilm_backend_emits_no_summary_request(client, tmp_path, spy):
    events = spy
    _set_default_selection({"type": "model", "id": "phi-4-mini"})

    scope = f"min-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Storage\nWAL.\n", encoding="utf-8")
    _post_artifact(client, scope, md, summary_backend="minilm")

    assert _summary_requests(events) == []


def test_no_selection_emits_no_summary_request(client, tmp_path, spy):
    events = spy
    # No per-artifact target, no app default ⇒ filename-only best-effort ⇒ no emit.

    scope = f"nos-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Storage\nWAL.\n", encoding="utf-8")
    _post_artifact(client, scope, md)

    assert _summary_requests(events) == []
