"""Regression (unified-ai-routing review): /comms/post must call index_artifact_async
with kwargs the function actually accepts.

Conv 5 removed the `summarize` param from index_artifact_async, but the post handler
kept passing `summarize=False`. That raised a synchronous TypeError which the handler's
`except Exception` swallowed (debug log only) — silently skipping markdown SECTION
INDEXING for every `.md` artifact posted via /comms/post. The full gate suite missed it
because other tests stub index_artifact_async with `lambda *a, **k` (whose **k absorbs the
bad kwarg). This test binds the call against the REAL signature, so a stale kwarg fails
loudly without depending on the async daemon thread.
"""

from __future__ import annotations

import inspect
import uuid

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_post_artifact_calls_indexer_with_valid_kwargs(client, tmp_path, monkeypatch):
    import pathly_orchestrator.runner.hydrate as hyd

    real_sig = inspect.signature(hyd.index_artifact_async)
    bind_errors: list[str] = []
    calls: list[tuple] = []

    def _wrapper(*a, **k):
        calls.append((a, k))
        try:
            real_sig.bind(*a, **k)  # validate against the real signature
        except TypeError as exc:
            bind_errors.append(str(exc))

    monkeypatch.setattr(hyd, "index_artifact_async", _wrapper)

    scope = f"idx-{uuid.uuid4().hex[:8]}"
    md = tmp_path / "DOC.md"
    md.write_text("# Doc\n## Storage\nWAL.\n", encoding="utf-8")
    r = client.post(
        "/comms/post",
        json={
            "feature": scope,
            "from": "human",
            "type": "artifact",
            "text": "DOC.md",
            "board": "feature",
            "scope": scope,
            "artifact_path": str(md).replace("\\", "/"),
            "artifact_type": "md",
        },
    )
    assert r.status_code == 200, r.data
    assert calls, "post path never called index_artifact_async"
    assert not bind_errors, f"stale kwargs passed to index_artifact_async: {bind_errors}"
    # Conv 5 removed `summarize`; guard against it (or any caller) coming back.
    assert "summarize" not in real_sig.parameters
