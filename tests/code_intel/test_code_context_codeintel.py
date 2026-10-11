"""The ``codeintel`` code-context backend (codeintel-backend).

Unlike the ``cli``/``lsp`` backends, which return the same per-file symbol-count
block for every op, ``codeintel`` answers the op that was asked (real caller rows,
semantic ``search``). These tests pin: the HTTP-daemon-then-subprocess transport
order, the never-raise contract, ``auto`` preferring codeintel, and that
``/code/query`` forwards op + engine to it (bypassing the legacy file cache).
"""

from __future__ import annotations

import pytest

from pathly_orchestrator.runner import code_context as cc
from pathly_orchestrator.runner import code_context_codeintel as ci

_ENVELOPE = {
    "ok": True,
    "op": "callers",
    "target": "build_block",
    "result": "## Callers of build_block (2 direct)\n- a.py:10 resolved",
    "engine": "graph",
    "cached": False,
    "outcome": "answered",
}


def test_http_answer_is_rendered_and_tagged():
    seen = {}

    def http(url, body, token):
        seen.update(body)
        return dict(_ENVELOPE)

    block, meta = ci.CodeintelProvider(http=http, cli=lambda b: None).query(
        "callers", "build_block", "", "auto"
    )
    assert "Callers of build_block" in block
    assert block.startswith("## codeintel")
    assert meta["transport"] == "http"
    # `auto` is not forwarded — codeintel picks the engine per op.
    assert seen["op"] == "callers" and seen["engine"] is None


def test_falls_back_to_cli_when_daemon_unreachable():
    block, meta = ci.CodeintelProvider(
        http=lambda u, b, t: None, cli=lambda b: dict(_ENVELOPE)
    ).query("callers", "build_block", engine="lsp")
    assert block and meta["transport"] == "cli"


def test_null_answer_passes_reason_through():
    null = {**_ENVELOPE, "result": None, "reason": "project-not-indexed", "hint": "run codeintel index"}
    block, meta = ci.CodeintelProvider(http=lambda u, b, t: null).query("callers", "x")
    assert block == ""
    assert meta["reason"] == "project-not-indexed"
    assert meta["hint"] == "run codeintel index"


def test_nothing_reachable_is_backend_unavailable():
    block, meta = ci.CodeintelProvider(http=lambda u, b, t: None, cli=lambda b: None).query(
        "callers", "x"
    )
    assert block == "" and meta["reason"] == "backend-unavailable"


def test_query_never_raises():
    def boom(*a):
        raise RuntimeError("wedged")

    block, meta = ci.CodeintelProvider(http=boom, cli=boom).query("callers", "x")
    assert block == "" and meta["reason"] == "backend-error"


def test_budget_truncates():
    block, _ = ci.CodeintelProvider(http=lambda u, b, t: dict(_ENVELOPE)).query(
        "callers", "x", budget=20
    )
    assert len(block) == 20


def test_auto_prefers_codeintel_when_installed(monkeypatch):
    have = {"codeintel", "codebase-memory-mcp", "uvx"}
    monkeypatch.setattr(cc.shutil, "which", lambda n: "/usr/bin/x" if n in have else None)
    assert cc._auto_backend() == "codeintel"
    assert cc.get_provider("codeintel").name == "codeintel"


def test_explicit_codeintel_setting_is_honoured(monkeypatch):
    monkeypatch.setattr(
        cc, "_get_setting", lambda k, d: "codeintel" if k == "code_context.backend" else d
    )
    assert cc._resolve_backend() == "codeintel"


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import _rate_counters, app

    _rate_counters.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_proxy_forwards_op_and_engine_to_codeintel(client, monkeypatch):
    calls = []

    def fake_query(self, op, target, project_root="", engine="", budget=6000):
        calls.append((op, target, engine, budget))
        return "## codeintel\nrows", {"engine": "semantic", "transport": "http"}

    monkeypatch.setattr(cc, "_resolve_backend", lambda: "codeintel")
    monkeypatch.setattr(ci.CodeintelProvider, "query", fake_query)
    for _ in range(2):  # no gateway cache: both requests reach codeintel
        r = client.post(
            "/code/query",
            json={"op": "search", "target": "auth middleware", "role": "builder",
                  "engine": "semantic", "scope": "(interactive)"},
        )
        body = r.get_json()
        assert r.status_code == 200 and body["backend"] == "codeintel"
        assert body["result"].startswith("## codeintel") and body["cached"] is False
    assert calls == [("search", "auth middleware", "semantic", 6000)] * 2


def test_proxy_engine_cli_still_reaches_legacy_backend(client, monkeypatch):
    monkeypatch.setattr(cc, "_resolve_backend", lambda: "codeintel")
    monkeypatch.setattr(
        ci.CodeintelProvider, "query", lambda *a, **k: pytest.fail("codeintel must not run")
    )
    monkeypatch.setattr(cc, "build_block", lambda *a, **k: "")
    r = client.post(
        "/code/query",
        json={"op": "callers", "target": "a.py", "role": "builder", "engine": "cli",
              "scope": "(interactive)"},
    )
    assert r.get_json()["backend"] == "cli"
