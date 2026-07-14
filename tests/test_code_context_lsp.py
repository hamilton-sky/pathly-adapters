"""The ``lsp`` backend (Serena) behind /code/query, and its dispatch wiring.

Covers the LspProvider render/warm-up/never-raise contract, the CompositeProvider
(``both``) merge, the get_provider / _resolve_backend dispatch, and the proxy
``engine`` routing + per-backend cache separation. Everything mocks the Serena
session, so no subprocess is spawned and the tests are host-independent.
"""

from __future__ import annotations

import json
import os

import pytest
from flask import Flask

# Platform-appropriate ABSOLUTE root (isabs is drive-letter on nt, leading-slash on
# POSIX) so the path assertions hold on Linux CI too — mirrors test_code_context_pathresolve.
_ABS = "D:/work/repo" if os.name == "nt" else "/work/repo"


# --- LspProvider ----------------------------------------------------------
def test_warmup_returns_empty(monkeypatch):
    """No ready session yet (boot in flight) → "" so the caller degrades to Grep."""
    import pathly_orchestrator.runner.code_context_lsp as lsp

    monkeypatch.setattr(lsp, "_get_ready_session", lambda root: None)
    assert lsp.LspProvider().build_block("s", ["src/x.py"], "architect", 1500, _ABS) == ""


def test_ready_renders_block(monkeypatch):
    import pathly_orchestrator.runner.code_context_lsp as lsp

    class FakeSession:
        def call_tool(self, name, arguments):
            assert name == "get_symbols_overview"
            assert "relative_path" in arguments
            return json.dumps(
                [{"name_path": "foo", "kind": 12}, {"name": "Bar", "kind": 5}]
            )

    monkeypatch.setattr(lsp, "_get_ready_session", lambda root: FakeSession())
    out = lsp.LspProvider().build_block("s", ["src/x.py"], "architect", 1500, _ABS)
    assert "## Code structure — LSP (advisory, always-fresh)" in out
    assert "- foo  (kind:12)" in out
    assert "- Bar  (kind:5)" in out


def test_never_raises_on_session_error(monkeypatch):
    import pathly_orchestrator.runner.code_context_lsp as lsp

    class BoomSession:
        def call_tool(self, name, arguments):
            raise RuntimeError("boom")

    monkeypatch.setattr(lsp, "_get_ready_session", lambda root: BoomSession())
    assert lsp.LspProvider().build_block("s", ["src/x.py"], "architect", 1500, _ABS) == ""


def test_empty_files_is_noop(monkeypatch):
    import pathly_orchestrator.runner.code_context_lsp as lsp

    called = {"n": 0}
    monkeypatch.setattr(
        lsp, "_get_ready_session", lambda root: called.__setitem__("n", called["n"] + 1)
    )
    assert lsp.LspProvider().build_block("s", [], "architect", 1500, _ABS) == ""
    assert called["n"] == 0  # no session boot attempted for an empty file list


def test_budget_truncates(monkeypatch):
    import pathly_orchestrator.runner.code_context_lsp as lsp

    class FakeSession:
        def call_tool(self, name, arguments):
            return json.dumps([{"name": "x" * 200}])

    monkeypatch.setattr(lsp, "_get_ready_session", lambda root: FakeSession())
    out = lsp.LspProvider().build_block("s", ["src/x.py"], "architect", 40, _ABS)
    assert len(out) <= 40


# --- render / relativize helpers -----------------------------------------
def test_render_overview_tolerates_shapes():
    from pathly_orchestrator.runner.code_context_lsp import _render_overview

    assert "- a" in _render_overview("f.py", json.dumps([{"name": "a"}]), 12)
    assert "- b" in _render_overview(
        "f.py", json.dumps({"symbols": [{"name": "b"}]}), 12
    )
    # dict-of-lists fallback
    assert "- c" in _render_overview("f.py", json.dumps({"anything": [{"name": "c"}]}), 12)
    assert _render_overview("f.py", "not json", 12) == ""  # unparseable → ""
    assert _render_overview("f.py", json.dumps([]), 12) == ""  # empty → ""


def test_render_overview_real_serena_shape():
    """Regression: live Serena get_symbols_overview returns {kind: [name, ...]}.

    Observed from Serena 1.27.0 — the renderer must handle a dict of kind →
    list-of-name-strings, not just list-of-dicts (the shape that silently rendered
    "" and made the first live run come back empty despite a healthy session).
    """
    from pathly_orchestrator.runner.code_context_lsp import _render_overview

    out = _render_overview(
        "app.py",
        json.dumps({"Class": ["Widget"], "Function": ["make_widget", "main"]}),
        12,
    )
    assert "- Widget  (kind:Class)" in out
    assert "- make_widget  (kind:Function)" in out
    assert "- main  (kind:Function)" in out


def test_relativize():
    from pathly_orchestrator.runner.code_context_lsp import _relativize

    assert _relativize(_ABS + "/src/x.py", _ABS) == "src/x.py"
    assert _relativize("src/x.py", _ABS) == "src/x.py"  # already relative → unchanged


# --- CompositeProvider (both) --------------------------------------------
def test_composite_merges_nonempty_blocks():
    from pathly_orchestrator.runner.code_context import CompositeProvider

    class P:
        def __init__(self, blk):
            self._blk = blk

        def build_block(self, *a, **k):
            return self._blk

    out = CompositeProvider([P("## graph\n- x"), P("## lsp\n- y")]).build_block(
        "s", ["f"], "r", 1500, "root"
    )
    assert "## graph" in out and "## lsp" in out


def test_composite_skips_failing_child():
    from pathly_orchestrator.runner.code_context import CompositeProvider

    class Boom:
        def build_block(self, *a, **k):
            raise RuntimeError("x")

    class Ok:
        def build_block(self, *a, **k):
            return "## ok\n- z"

    assert CompositeProvider([Boom(), Ok()]).build_block(
        "s", ["f"], "r", 1500, "root"
    ) == "## ok\n- z"


# --- dispatch: get_provider / _resolve_backend / build_block override -----
def test_get_provider_lsp_and_both():
    from pathly_orchestrator.runner import code_context as cc

    assert cc.get_provider("lsp").name == "lsp"
    assert cc.get_provider("both").name == "both"
    assert cc.get_provider("off").name == "none"


def test_resolve_backend_allows_lsp_and_both(monkeypatch):
    from pathly_orchestrator.runner import code_context as cc

    monkeypatch.setattr(cc, "_get_setting", lambda k, d: "lsp")
    assert cc._resolve_backend() == "lsp"
    monkeypatch.setattr(cc, "_get_setting", lambda k, d: "both")
    assert cc._resolve_backend() == "both"
    monkeypatch.setattr(cc, "_get_setting", lambda k, d: "bogus")
    assert cc._resolve_backend() == "none"


def test_build_block_backend_override_wins(monkeypatch):
    """An explicit backend arg overrides the configured one."""
    from pathly_orchestrator.runner import code_context as cc

    seen = {}

    class Spy:
        name = "spy"

        def build_block(self, scope, files, role, budget, project_root=""):
            seen["hit"] = True
            return "spy-block"

    monkeypatch.setattr(cc, "_resolve_backend", lambda: "none")  # config says off
    monkeypatch.setattr(cc, "get_provider", lambda b: Spy() if b == "lsp" else cc.NoneProvider())
    assert cc.build_block("s", ["f"], "r", 1500, _ABS, backend="lsp") == "spy-block"
    assert seen.get("hit") is True


# --- proxy: engine routing + per-backend cache separation -----------------
@pytest.fixture()
def client():
    from pathly_orchestrator.http_server.blueprints.code.query import bp

    app = Flask(__name__)
    app.register_blueprint(bp)
    return app.test_client()


def test_engine_lsp_routes_backend(client, monkeypatch):
    import pathly_orchestrator.runner.code_context as cc
    from pathly_orchestrator.http_server.blueprints.code import query as q

    q._QUERY_CACHE.clear()
    monkeypatch.setattr(cc, "maybe_reindex", lambda *a, **k: None)
    seen = {}

    def fake_build_block(scope, files, role, budget, project_root="", backend=None):
        seen["backend"] = backend
        return "## Code structure — LSP\n### f\n- x"

    monkeypatch.setattr(cc, "build_block", fake_build_block)
    resp = client.post(
        "/code/query",
        json={"op": "symbol", "target": "src/x.py", "role": "architect",
              "engine": "lsp", "project_root": _ABS},
    )
    data = resp.get_json()
    assert seen["backend"] == "lsp"
    assert data["backend"] == "lsp"
    assert data["result"] is not None


def test_cache_separates_by_backend(client, monkeypatch):
    import pathly_orchestrator.runner.code_context as cc
    from pathly_orchestrator.http_server.blueprints.code import query as q

    q._QUERY_CACHE.clear()
    monkeypatch.setattr(cc, "maybe_reindex", lambda *a, **k: None)
    calls = []

    def fake_build_block(scope, files, role, budget, project_root="", backend=None):
        calls.append(backend)
        return f"block-for-{backend}"

    monkeypatch.setattr(cc, "build_block", fake_build_block)
    base = {"op": "symbol", "target": "src/x.py", "role": "architect", "project_root": _ABS}
    r1 = client.post("/code/query", json={**base, "engine": "graph"}).get_json()
    r2 = client.post("/code/query", json={**base, "engine": "lsp"}).get_json()
    # Same (op,target) but different engine → NOT a cache collision; both ran.
    assert r1["backend"] == "cli" and r2["backend"] == "lsp"
    assert calls == ["cli", "lsp"]
    assert r1["result"] == "block-for-cli" and r2["result"] == "block-for-lsp"


def test_null_result_not_cached(client, monkeypatch):
    """A warming-up/not-yet-indexed null must NOT be pinned — it re-queries so the
    block appears once the async index lands (regression for the auto-onboard race)."""
    import pathly_orchestrator.runner.code_context as cc
    from pathly_orchestrator.http_server.blueprints.code import query as q

    q._QUERY_CACHE.clear()
    monkeypatch.setattr(cc, "maybe_reindex", lambda *a, **k: None)
    calls = {"n": 0}
    outputs = ["", "## block\n- x"]  # first null (indexing), then real

    def fake_build_block(scope, files, role, budget, project_root="", backend=None):
        i = calls["n"]
        calls["n"] += 1
        return outputs[min(i, len(outputs) - 1)]

    monkeypatch.setattr(cc, "build_block", fake_build_block)
    body = {"op": "symbol", "target": "x.py", "role": "architect",
            "engine": "graph", "project_root": _ABS}
    r1 = client.post("/code/query", json=body).get_json()
    r2 = client.post("/code/query", json=body).get_json()
    r3 = client.post("/code/query", json=body).get_json()
    assert r1["result"] is None  # warming up → null, not cached
    assert r2["result"] == "## block\n- x"  # re-queried (null was NOT served) → real
    assert r3["result"] == "## block\n- x"  # now cached
    assert calls["n"] == 2  # r1 + r2 hit the backend; r3 served from cache


def test_unknown_engine_falls_through_to_config(client, monkeypatch):
    import pathly_orchestrator.runner.code_context as cc
    from pathly_orchestrator.http_server.blueprints.code import query as q

    q._QUERY_CACHE.clear()
    monkeypatch.setattr(cc, "maybe_reindex", lambda *a, **k: None)
    monkeypatch.setattr(cc, "_resolve_backend", lambda: "none")
    seen = {}

    def fake_build_block(scope, files, role, budget, project_root="", backend=None):
        seen["backend"] = backend
        return ""

    monkeypatch.setattr(cc, "build_block", fake_build_block)
    resp = client.post(
        "/code/query",
        json={"op": "symbol", "target": "src/x.py", "role": "architect",
              "engine": "wat", "project_root": _ABS},
    )
    data = resp.get_json()
    assert seen["backend"] is None  # unknown engine → no override → config used
    assert data["backend"] == "none"
    assert data["result"] is None
