"""Tests for HQ model eligibility and settings (hq-copilot ticket 05).

The DB is auto-isolated per test by tests/conftest.py.
"""

from __future__ import annotations

import pytest

SCOPE = "hqmodels"


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _seed(conn):
    from pathly_orchestrator.db.queries.comms import post_message

    post_message(
        conn,
        board="feature",
        scope=SCOPE,
        from_agent="planner",
        type="goal",
        text="Goal: pick a model",
        executor="single",
    )


def test_default_settings_resolve():
    # NOTE: ticket 01 settled hq.default_model = "qwen3-8b"; the Done-when
    # line naming phi-4-mini was written before that settlement and is stale.
    from pathly_orchestrator import hq_models

    assert hq_models.hq_default_model() == "qwen3-8b"
    assert hq_models.hq_budget_tokens() == 6000


def test_settings_overrides_and_garbage_fallback():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.hq_settings import (
        get_hq_budget_tokens,
        get_hq_default_model,
        get_hq_packet_order,
        set_hq_packet_order,
        set_setting,
    )

    conn = get_db()
    set_setting(conn, "hq.default_model", "phi-4-mini")
    set_setting(conn, "hq.context_budget_tokens", "3000")
    assert get_hq_default_model(conn) == "phi-4-mini"
    assert get_hq_budget_tokens(conn) == 3000

    set_setting(conn, "hq.context_budget_tokens", "not-a-number")
    assert get_hq_budget_tokens(conn) == 6000

    set_hq_packet_order(conn, "progress")
    assert get_hq_packet_order(conn) == "progress"
    with pytest.raises(ValueError):
        set_hq_packet_order(conn, "sideways")


def test_eligibility_windows():
    from pathly_orchestrator import hq_models

    # 128k window is eligible at the default budget (needs 16000).
    assert hq_models.hq_eligible("phi-4-mini", 6000) is True
    # The default model (32k) clears the default budget comfortably.
    assert hq_models.hq_eligible("qwen3-8b", 6000) is True
    # Unknown models fail closed.
    assert hq_models.hq_eligible("no-such-model", 6000) is False
    assert hq_models.hq_eligible("", 6000) is False


def test_small_window_ineligible(monkeypatch):
    from pathly_orchestrator import hq_models

    monkeypatch.setitem(hq_models.MODEL_CONTEXT_WINDOWS, "tiny-4k", 4096)
    assert hq_models.hq_eligible("tiny-4k", 6000) is False
    # ...but it would pass a tiny budget (needs 2*40+4000=4080 <= 4096).
    assert hq_models.hq_eligible("tiny-4k", 40) is True


def test_endpoint_reports_eligibility(client):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator import hq_models

    _seed(get_db())
    r = client.get(f"/hq/context?board={SCOPE}&model=phi-4-mini")
    assert r.status_code == 200
    data = r.get_json()
    assert data["model"] == "phi-4-mini"
    assert data["eligible_model"] is True
    assert data["eligible_model"] == hq_models.hq_eligible("phi-4-mini", 6000)

    r = client.get(f"/hq/context?board={SCOPE}&model=no-such-model")
    assert r.get_json()["eligible_model"] is False

    # No ?model= → the configured default is reported.
    r = client.get(f"/hq/context?board={SCOPE}")
    assert r.get_json()["model"] == "qwen3-8b"
    assert r.get_json()["eligible_model"] is True
