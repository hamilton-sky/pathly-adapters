"""Tests for board_context_for — scope-aware context honoring the Reads toggle.

`board_context_for()` is the shared helper that single-agent, loop-executor, and
/comms/run agents call so they consume the SAME board governance + memory the
FSM/team path already injects. It resolves the per-feature board_scope selection
(the Studio "Reads:" toggles) and only injects the enabled tiers.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embeddings: no async daemon (avoids DB-reset races) and force the
    recency path so the test does not need a real embedding model."""
    import pathly_orchestrator.runner.embeddings as _emb_mod
    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)
    monkeypatch.setattr(_emb_mod, "embed", lambda *a, **k: None)


def test_board_context_for_honors_reads_toggle():
    """Feature tier OFF drops feature content but keeps the selected project tier."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.db.queries.app_settings import set_board_scope
    from pathly_orchestrator.runner.comms_context import board_context_for

    conn = get_db()
    topic = "demo"
    root = "C:/proj"

    post_message(conn, board="feature", scope=topic, from_agent="human",
                 type="decision", text="FEATURE-LEVEL rule")
    post_message(conn, board="project", scope=root, from_agent="human",
                 type="decision", text="PROJECT-LEVEL rule")

    # Reads: feature OFF, project ON, global ON.
    set_board_scope(conn, root, topic, {"feature": False, "project": True, "global": True})

    block = board_context_for("feature", topic, root, "do the work")

    assert "PROJECT-LEVEL rule" in block, "selected project tier should appear"
    assert "FEATURE-LEVEL rule" not in block, "deselected feature tier must be excluded"


def test_board_context_for_defaults_to_all_tiers():
    """With no stored toggle, all tiers are enabled (default-on)."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.runner.comms_context import board_context_for

    conn = get_db()
    post_message(conn, board="feature", scope="demo2", from_agent="human",
                 type="decision", text="DEFAULT feature rule")

    block = board_context_for("feature", "demo2", "C:/proj", "do the work")
    assert "DEFAULT feature rule" in block


def test_board_context_for_project_board_skips_feature_tier():
    """A project-board run pulls the project tier, never a feature topic."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.runner.comms_context import board_context_for

    conn = get_db()
    root = "C:/proj"
    post_message(conn, board="feature", scope="some-feature", from_agent="human",
                 type="decision", text="A FEATURE rule")
    post_message(conn, board="project", scope=root, from_agent="human",
                 type="decision", text="A PROJECT rule")

    block = board_context_for("project", root, root, "do the work")

    assert "A PROJECT rule" in block
    assert "A FEATURE rule" not in block, "project-board run must not pull a feature topic"
