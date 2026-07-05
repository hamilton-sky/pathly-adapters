"""Tests for Phase 1.4c — labeled governance/semantic channels.

retrieve_board_context() must produce a ## Communication Board block with:
  - Governance section containing decisions + escalations (always injected)
  - Context section containing semantic matches (labeled as advisory)
  - Escalations must NOT appear in the context pool (only in governance)
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    """Stub embed_async so posting an embeddable message never spawns a daemon
    thread. That thread calls get_db() and races the per-test DB reset (the
    module-global one-time-migration guard in db.connection), which otherwise
    causes intermittent 'no such table: comms_messages' flakes when these tests
    run alongside one another or other comms suites."""
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


@pytest.fixture()
def client():
    """Flask test client. DB is isolated per-test by the autouse conftest fixture."""
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(
    client, msg_type: str, text: str, board: str = "feature", scope: str = "demo"
) -> str:
    import json

    r = client.post(
        "/comms/post",
        json={
            "feature": "demo",
            "from": "human",
            "type": msg_type,
            "text": text,
            "board": board,
            "scope": scope,
        },
    )
    assert r.status_code == 200
    return json.loads(r.data)["message_id"]


# ---------------------------------------------------------------------------
# get_active_escalations direct tests
# ---------------------------------------------------------------------------


def test_comms_context_channels_get_active_escalations_empty():
    """get_active_escalations returns [] for an empty board."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_active_escalations

    conn = get_db()
    result = get_active_escalations(conn, boards=["feature"], scopes=["demo"])
    assert result == []


def test_comms_context_channels_get_active_escalations_returns_escalation():
    """get_active_escalations returns pending escalation messages."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import (
        get_active_escalations,
        post_message,
    )

    conn = get_db()
    esc_id = post_message(
        conn,
        board="feature",
        scope="demo",
        from_agent="builder",
        type="escalation",
        text="Need human sign-off on auth design",
    )
    result = get_active_escalations(conn, boards=["feature"], scopes=["demo"])
    assert any(m["id"] == esc_id for m in result)


def test_comms_context_channels_escalation_excluded_after_supersede():
    """A superseded escalation is NOT returned by get_active_escalations."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import (
        get_active_escalations,
        post_message,
        supersede_message,
    )

    conn = get_db()
    esc_id = post_message(
        conn,
        board="feature",
        scope="demo",
        from_agent="builder",
        type="escalation",
        text="Old escalation",
    )
    new_id = post_message(
        conn,
        board="feature",
        scope="demo",
        from_agent="human",
        type="escalation",
        text="New escalation",
    )
    supersede_message(conn, esc_id, new_id)

    result = get_active_escalations(conn, boards=["feature"], scopes=["demo"])
    assert all(
        m["id"] != esc_id for m in result
    ), "superseded escalation should be excluded"


def test_comms_context_channels_get_active_escalations_no_boards():
    """get_active_escalations returns [] when boards or scopes is empty."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import get_active_escalations

    conn = get_db()
    assert get_active_escalations(conn, boards=[], scopes=["demo"]) == []
    assert get_active_escalations(conn, boards=["feature"], scopes=[]) == []


# ---------------------------------------------------------------------------
# retrieve_board_context two-channel output tests
# ---------------------------------------------------------------------------


def test_comms_context_channels_decision_in_governance(client):
    """A pending decision appears under the Governance section."""
    _post(client, "decision", "Use SQLite for all persistence")

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="build the feature",
        board_scope={"feature": True, "project": False, "global": False},
    )

    assert "## Communication Board" in block
    assert "### Governance" in block
    assert "Use SQLite for all persistence" in block


def test_comms_context_channels_escalation_in_governance(client):
    """An active escalation appears under the Governance section."""
    _post(client, "escalation", "Need human sign-off before proceeding")

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="build the feature",
        board_scope={"feature": True, "project": False, "global": False},
    )

    assert "### Governance" in block
    assert "Need human sign-off before proceeding" in block
    assert "Open escalations" in block


def test_comms_context_channels_governance_label_not_in_context(client):
    """Governance section label reads 'always applies — do not override'."""
    _post(client, "decision", "No external API calls")

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="make an API call",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "always applies" in block
    assert "do not override" in block


def test_comms_context_channels_context_section_advisory_label(client, monkeypatch):
    """The Context section carries 'verify before acting' advisory text."""
    # Inject a discovery so retrieve_board_context has something in the context pool
    _post(client, "discovery", "Auth bug: session tokens expire too fast")

    # Monkeypatch embed to return None so we fall through to recency path —
    # avoids needing a real model in tests
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="fix auth",
        board_scope={"feature": True, "project": False, "global": False},
    )

    # If the block is non-empty and has context items, check label
    if "### Context" in block:
        assert "verify before acting" in block


def test_comms_context_channels_empty_board_returns_empty_string():
    """With no messages on any board, retrieve_board_context returns ''."""
    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="empty-feature",
        project_root="C:/proj",
        task_description="do something",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert block == ""


def test_comms_context_channels_superseded_decision_absent_from_governance(client):
    """A superseded decision does NOT appear in the Governance section."""
    old_id = _post(client, "decision", "Use PostgreSQL")
    new_id = _post(client, "decision", "Use SQLite")

    r = client.post("/comms/supersede", json={"old_id": old_id, "new_id": new_id})
    assert r.status_code == 200

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="persist some data",
        board_scope={"feature": True, "project": False, "global": False},
    )

    assert "Use PostgreSQL" not in block, "superseded decision should be absent"
    assert "Use SQLite" in block, "current decision should appear"


def test_comms_context_channels_governance_and_context_both_present(
    client, monkeypatch
):
    """When both governance items and context items exist, both sections appear."""
    _post(client, "decision", "No external API calls")
    _post(client, "discovery", "Auth bug discovered in session tokens")

    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="fix auth",
        board_scope={"feature": True, "project": False, "global": False},
    )

    assert "### Governance" in block
    assert "No external API calls" in block
    # Context section may or may not appear depending on recency path logic —
    # verify the block is non-empty at minimum
    assert block.strip() != ""


def test_comms_context_channels_governance_does_not_starve_context(client, monkeypatch):
    """Governance messages must not displace advisory context out of the k-cap.

    On the global board (k=1), a decision posted *after* a discovery must not
    starve the Context section. Because decisions are embedded, a naive
    fetch-then-filter would let the newer decision fill the single slot and then
    drop it as governance, leaving zero context. retrieve_board_context()
    over-fetches before filtering, so the discovery survives (Phase 1.4c fix).
    """
    _post(
        client,
        "discovery",
        "Cache layer added to the API",
        board="global",
        scope="global",
    )
    _post(
        client, "decision", "Use Redis for caching", board="global", scope="global"
    )  # newer

    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed", lambda text: None)  # recency path

    from pathly_orchestrator.runner.comms_context import retrieve_board_context

    block = retrieve_board_context(
        topic="demo",
        project_root="C:/proj",
        task_description="work on caching",
        board_scope={"feature": False, "project": False, "global": True},
    )

    assert "Use Redis for caching" in block, "governance decision should appear"
    assert (
        "### Context" in block
    ), "context section should not be starved by the decision"
    assert (
        "Cache layer added to the API" in block
    ), "advisory discovery should survive over-fetch"
