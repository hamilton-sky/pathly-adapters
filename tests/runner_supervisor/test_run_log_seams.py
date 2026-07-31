"""run_log write seams — best-effort spawn + result persistence (unified-control-plane P0,
ARCHITECTURE §3.2-3.3, AC-6).

Two seams populate run_log: ``write_run_log_spawn`` beside ``_record_spawn_identity`` in the
spawn path (terminal.py), and ``update_run_log_stdout`` right before the result callback drops
stdout (api_lifecycle.py). Both are best-effort: a raising write must NEVER fail the run.

These tests fault-inject the RESULT-path store to prove the ``/runner/terminal/result`` callback
still returns 200, and confirm a normal result fills the stdout half of the run's row. The
SPAWN-path seam uses the identical guarded idiom as the adjacent, already-proven
``_record_spawn_identity`` best-effort block (only ``logger.debug`` on failure), so it carries
the same guarantee.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Flask test client with a clean supervisor registry (DB isolated by conftest)."""
    monkeypatch.setenv("PATHLY_PROJECT_ROOT", str(tmp_path))
    from pathly_orchestrator.http_server import app
    from pathly_orchestrator.supervisor import _lock, _registry

    with _lock:
        _registry.clear()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, tmp_path
    with _lock:
        _registry.clear()


def _register_run(tmp_path, topic: str, run_id: str):
    from pathly_orchestrator.supervisor import RunnerState, _lock, _registry
    from pathly_orchestrator.supervisor.registry import create_run

    with _lock:
        st = RunnerState(
            topic=topic, flow="consultation", project_root=str(tmp_path),
            model="m", timeout=60, run_id=run_id,
        )
        st.status = "running"
        _registry[topic] = st
    create_run(run_id)


def test_result_callback_completes_when_stdout_write_raises(client, monkeypatch):
    """AC-6: patching ``update_run_log_stdout`` to raise must NOT fail the result callback —
    the write is best-effort (try/except → logger.debug), never gating the 200."""
    c, tmp_path = client
    from unittest.mock import MagicMock

    import pathly_orchestrator.db.queries.run_log as run_log_mod
    from pathly_orchestrator.supervisor.registry import drop_run

    monkeypatch.setattr(
        run_log_mod,
        "update_run_log_stdout",
        MagicMock(side_effect=RuntimeError("run_log stdout write blew up")),
    )

    topic, run_id = "ac6-stdout-raise", "run-ac6-raise"
    _register_run(tmp_path, topic, run_id)
    try:
        r = c.post(
            "/runner/terminal/result",
            json={
                "topic": topic, "run_id": run_id, "exit_code": 0,
                "stdout_tail": "some output", "user_initiated": False,
            },
        )
        assert r.status_code == 200  # callback completed despite the raising write
    finally:
        drop_run(run_id)


def test_result_callback_fills_stdout_for_run(client):
    """A normal result POST fills the stdout half of the run's spawn-time run_log row,
    leaving the spawn-half fields (prompt_sent) intact."""
    c, tmp_path = client
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_log import get_run_log, write_run_log_spawn
    from pathly_orchestrator.supervisor.registry import drop_run

    topic, run_id = "ac6-stdout-fill", "run-ac6-fill"
    _register_run(tmp_path, topic, run_id)
    # a spawn-half row already exists (as write-point A would have written at spawn)
    write_run_log_spawn(get_db(), run_id, stage="BUILDING", prompt_sent="the prompt")
    try:
        r = c.post(
            "/runner/terminal/result",
            json={
                "topic": topic, "run_id": run_id, "exit_code": 0,
                "stdout_tail": "the captured stdout tail", "user_initiated": False,
            },
        )
        assert r.status_code == 200
        rows = get_run_log(get_db(), run_id)
        assert len(rows) == 1  # UPDATE, not a second INSERT
        assert rows[0]["stdout"] == "the captured stdout tail"
        assert rows[0]["prompt_sent"] == "the prompt"  # spawn-half survives
    finally:
        drop_run(run_id)
