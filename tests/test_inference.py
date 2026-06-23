"""Phase 4 — offline summarizer (runner/inference.py), backend selection, writeback.

Covers the §1–§3 interface, the §6 scope guard (.md-only, never-raises, no auto-start),
and the §7/§8 behavior-preserving guarantee: with the default `minilm` backend, no
summary is generated and the seeded summary is never overwritten.
"""

from __future__ import annotations

import json

import pytest


class _SyncThread:
    """Run the daemon worker synchronously so fire-and-forget is testable."""

    def __init__(self, target=None, daemon=None, **kw):
        self._target = target

    def start(self):
        if self._target is not None:
            self._target()


# ---------------------------------------------------------------------------
# Backend selection (db/queries/app_settings.py §3)
# ---------------------------------------------------------------------------


def test_summary_backend_default_minilm(monkeypatch):
    monkeypatch.delenv("PATHLY_SUMMARY_BACKEND", raising=False)
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import get_summary_backend

    assert get_summary_backend(get_db()) == "minilm"


def test_summary_backend_roundtrip(monkeypatch):
    monkeypatch.delenv("PATHLY_SUMMARY_BACKEND", raising=False)
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import (
        get_summary_backend,
        set_summary_backend,
    )

    conn = get_db()
    set_summary_backend(conn, "haiku")
    assert get_summary_backend(conn) == "haiku"


def test_summary_backend_invalid_raises():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import set_summary_backend

    with pytest.raises(ValueError):
        set_summary_backend(get_db(), "gpt5")


def test_summary_backend_env_fallback(monkeypatch):
    """No app_settings row → the PATHLY_SUMMARY_BACKEND env var wins over the default."""
    monkeypatch.setenv("PATHLY_SUMMARY_BACKEND", "ollama")
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.app_settings import get_summary_backend

    assert get_summary_backend(get_db()) == "ollama"


# ---------------------------------------------------------------------------
# summarize_content dispatch (§2, §6 — never raises, .md only)
# ---------------------------------------------------------------------------


def test_non_md_returns_none():
    from pathly_orchestrator.runner.inference import summarize_content

    r = summarize_content("whatever", artifact_type="code", backend="haiku")
    assert r.summary is None and r.backend == "none"


def test_minilm_returns_none():
    from pathly_orchestrator.runner.inference import summarize_content

    r = summarize_content("# Doc\n## Phase 1\nbody", backend="minilm")
    assert r.summary is None and r.backend == "minilm"


def test_ollama_success(monkeypatch):
    import pathly_orchestrator.runner.inference as inf

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"response": "Covers: phase 1 setup."}).encode()

    monkeypatch.setattr(inf.urllib.request, "urlopen", lambda *a, **k: _Resp())
    r = inf.summarize_content("# Doc\n## Phase 1\nx", backend="ollama")
    assert r.backend == "ollama" and r.summary == "Covers: phase 1 setup."


def test_ollama_unreachable_no_raise(monkeypatch):
    import pathly_orchestrator.runner.inference as inf

    def _boom(*a, **k):
        raise inf.urllib.error.URLError("connection refused")

    monkeypatch.setattr(inf.urllib.request, "urlopen", _boom)
    r = inf.summarize_content("# Doc\n## Phase 1\nx", backend="ollama")
    # Honest, mode-specific message (server-down vs model-missing) — never raises.
    assert r.summary is None and r.error is not None and "ollama" in r.error.lower()


def test_ollama_model_missing_message(monkeypatch):
    """A 404 from Ollama (model not pulled) must say so, not 'unreachable'."""
    import pathly_orchestrator.runner.inference as inf

    def _http404(*a, **k):
        raise inf.urllib.error.HTTPError("url", 404, "not found", None, None)  # type: ignore[arg-type]

    monkeypatch.setattr(inf.urllib.request, "urlopen", _http404)
    r = inf.summarize_content("# Doc\n## Phase 1\nx", backend="ollama")
    assert r.summary is None and r.error is not None and "pull" in r.error.lower()


def test_haiku_success(monkeypatch):
    import pathly_orchestrator.runner.argv as argv_mod
    import pathly_orchestrator.runner.inference as inf
    import pathly_orchestrator.runner.output as out_mod

    class _Out:
        stdout = "{}"

    monkeypatch.setattr(argv_mod, "resolve_argv", lambda *a, **k: ["claude", "-p", "x"])
    monkeypatch.setattr(inf.subprocess, "run", lambda *a, **k: _Out())
    monkeypatch.setattr(
        out_mod, "parse_result", lambda adapter, raw: {"result": "Covers: X", "cost_usd": 0.001}
    )
    r = inf.summarize_content("# Doc\n## Phase 1\nx", backend="haiku")
    assert r.backend == "haiku" and r.summary == "Covers: X" and r.cost_usd == 0.001


def test_haiku_error_no_raise(monkeypatch):
    import pathly_orchestrator.runner.inference as inf

    def _boom(*a, **k):
        raise RuntimeError("argv fail")

    monkeypatch.setattr(inf.subprocess, "run", _boom)
    r = inf.summarize_content("# Doc\n## Phase 1\nx", backend="haiku")
    assert r.summary is None and r.error is not None  # never raises


# ---------------------------------------------------------------------------
# Writeback hooks (db/queries/comms.py)
# ---------------------------------------------------------------------------


def _seed_artifact(conn, summary="seed"):
    from pathly_orchestrator.db.queries.comms import insert_artifact, post_message

    mid = post_message(
        conn, board="feature", scope="s", from_agent="planner", type="artifact", text="seed"
    )
    aid = insert_artifact(
        conn, message_id=mid, path="pathly/plans/s/EDGE.md", type="md", summary=summary
    )
    return mid, aid


def test_update_artifact_summary_writeback():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import update_artifact_summary

    conn = get_db()
    _mid, aid = _seed_artifact(conn)
    update_artifact_summary(conn, aid, "Covers: phase 1.")
    row = conn.execute("SELECT summary FROM comms_artifacts WHERE id=?", (aid,)).fetchone()
    assert row["summary"] == "Covers: phase 1."


def test_update_section_summary_writeback():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import (
        get_artifact_sections,
        reindex_artifact_sections,
        update_section_summary,
    )

    conn = get_db()
    _mid, aid = _seed_artifact(conn)
    reindex_artifact_sections(
        conn,
        aid,
        [
            {
                "id": "sec1",
                "anchor": "phase-1",
                "heading": "## Phase 1",
                "line_start": 1,
                "line_end": 2,
                "ordinal": 0,
            }
        ],
        0.0,
        "hash",
        "phase-1",
    )
    update_section_summary(conn, "sec1", "Phase 1 blurb.")
    secs = get_artifact_sections(conn, aid)
    assert any(s["summary"] == "Phase 1 blurb." for s in secs)


# ---------------------------------------------------------------------------
# Behavior-preserving guarantee (§7/§8) — the load-bearing check
# ---------------------------------------------------------------------------


def test_summarize_async_minilm_does_not_overwrite(monkeypatch):
    """Default minilm → summarize_content returns None → seeded summary is untouched."""
    import pathly_orchestrator.runner.inference as inf
    from pathly_orchestrator.db.connection import get_db

    # Establish the connection (and its WAL-checkpoint thread) BEFORE patching
    # threading.Thread, so only summarize_async's worker runs synchronously.
    conn = get_db()
    mid, aid = _seed_artifact(conn, summary="original seed text")
    monkeypatch.setattr(inf.threading, "Thread", _SyncThread)
    inf.summarize_async(aid, mid, "# Doc\n## Phase 1\nbody", backend="minilm")
    row = conn.execute("SELECT summary FROM comms_artifacts WHERE id=?", (aid,)).fetchone()
    assert row["summary"] == "original seed text"  # unchanged — minilm wrote nothing


def test_summarize_async_generative_writes(monkeypatch):
    """A generative backend → summarize_async writes the produced summary."""
    import pathly_orchestrator.runner.inference as inf
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    mid, aid = _seed_artifact(conn, summary="seed")
    monkeypatch.setattr(inf.threading, "Thread", _SyncThread)
    monkeypatch.setattr(
        inf, "summarize_content", lambda *a, **k: inf.SummaryResult("Covers: topic map.", "haiku")
    )
    inf.summarize_async(aid, mid, "text", backend="haiku")
    row = conn.execute("SELECT summary FROM comms_artifacts WHERE id=?", (aid,)).fetchone()
    assert row["summary"] == "Covers: topic map."
