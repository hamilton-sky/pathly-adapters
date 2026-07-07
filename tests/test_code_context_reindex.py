"""maybe_reindex freshness bridge.

Regression for the "Auto re-index doesn't refresh the graph" bug: `auto` used to only
flip the tool's own `auto_index` flag and defer freshness to the tool — but the tool's
change-detection silently misses edits, so the graph drifted stale. `auto` now runs the
incremental `index_repository` itself (+ sets the flag once), debounced so on-demand
/code/query calls don't spawn a subprocess per request.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def cc(monkeypatch):
    import pathly_orchestrator.runner.code_context as _cc

    monkeypatch.setattr(_cc, "_resolve_backend", lambda: "cli")
    monkeypatch.setattr(_cc, "_resolve_tool", lambda: "codebase-memory-mcp")
    monkeypatch.setattr(_cc.shutil, "which", lambda _t: "exe")
    _cc._last_reindex_monotonic = 0.0
    _cc._auto_index_done = False

    class _SyncThread:  # run the bg work synchronously so subprocess calls are captured
        def __init__(self, target=None, daemon=None):
            self._t = target

        def start(self):
            self._t()

    monkeypatch.setattr("threading.Thread", _SyncThread)
    return _cc


def _capture(cc, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(cc.subprocess, "run", lambda argv, **k: calls.append(list(argv)))
    return calls


def test_auto_runs_incremental_index_and_sets_flag(cc, monkeypatch):
    monkeypatch.setattr(cc, "_resolve_reindex", lambda: "auto")
    calls = _capture(cc, monkeypatch)
    cc.maybe_reindex("D:/work/myrepo")
    joined = [" ".join(a) for a in calls]
    assert any("index_repository" in c for c in joined), joined   # actually re-indexes
    assert any("auto_index" in c for c in joined), joined          # + flag once


def test_stage_runs_incremental_index(cc, monkeypatch):
    monkeypatch.setattr(cc, "_resolve_reindex", lambda: "stage")
    calls = _capture(cc, monkeypatch)
    cc.maybe_reindex("D:/work/myrepo")
    assert any("index_repository" in " ".join(a) for a in calls)


def test_off_does_nothing(cc, monkeypatch):
    monkeypatch.setattr(cc, "_resolve_reindex", lambda: "off")
    calls = _capture(cc, monkeypatch)
    cc.maybe_reindex("D:/work/myrepo")
    assert calls == []


def test_debounced_within_window(cc, monkeypatch):
    monkeypatch.setattr(cc, "_resolve_reindex", lambda: "auto")
    calls = _capture(cc, monkeypatch)
    cc.maybe_reindex("D:/work/myrepo")
    n = len(calls)
    cc.maybe_reindex("D:/work/myrepo")  # immediately again → inside the debounce window
    assert len(calls) == n


def test_backend_off_is_noop(cc, monkeypatch):
    monkeypatch.setattr(cc, "_resolve_backend", lambda: "none")
    monkeypatch.setattr(cc, "_resolve_reindex", lambda: "auto")
    calls = _capture(cc, monkeypatch)
    cc.maybe_reindex("D:/work/myrepo")
    assert calls == []
