"""chief-autopilot 03: a run's token never reaches stored text through the write routes.

A headless agent once ran ``echo "PATHLY_RUN_TOKEN: $PATHLY_RUN_TOKEN"`` and its output reached
``run_log.stdout``, which ``GET /runs/<id>`` shows to any reader. After a
``/runner/terminal/result``, a ``/runner/event`` ``AGENT_DONE`` and a direct ``append_event``
whose text holds the run's token, no row of ``fsm_events``, ``run_log`` or ``comms_messages``
holds it.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb_mod

    monkeypatch.setattr(_emb_mod, "embed_async", lambda *a, **k: None)


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
            topic=topic,
            flow="consultation",
            project_root=str(tmp_path),
            model="m",
            timeout=60,
            run_id=run_id,
        )
        st.status = "running"
        _registry[topic] = st
    create_run(run_id)


def _stored_text(conn) -> list[str]:
    out: list[str] = []
    for sql in (
        "SELECT * FROM fsm_events",
        "SELECT * FROM run_log",
        "SELECT * FROM comms_messages",
    ):
        for row in conn.execute(sql).fetchall():
            out.extend(str(v) for v in tuple(row) if v is not None)
    return out


def test_no_stored_row_holds_the_runs_token(client):
    c, tmp_path = client
    from pathly_orchestrator import eventlog
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.run_log import get_run_log, write_run_log_spawn
    from pathly_orchestrator.db.queries.run_tokens import mint_run_token
    from pathly_orchestrator.db.secret_scan import REDACTED
    from pathly_orchestrator.supervisor.registry import drop_run

    conn = get_db()
    topic, run_id = "redact-topic", "run-redact-1"
    token = mint_run_token(
        conn, run_id, "builder", topic, str(tmp_path), "feature", topic
    )
    _register_run(tmp_path, topic, run_id)
    write_run_log_spawn(
        conn, run_id, stage="BUILDING", prompt_sent="run with $PATHLY_RUN_TOKEN"
    )
    try:
        r = c.post(
            "/runner/terminal/result",
            json={
                "topic": topic,
                "run_id": run_id,
                "exit_code": 0,
                "stdout_tail": f"PATHLY_RUN_TOKEN: {token}\nraw {token} end",
                "user_initiated": False,
            },
        )
        assert r.status_code == 200
        r = c.post(
            "/runner/event",
            json={
                "type": "AGENT_DONE",
                "feature": topic,
                "project_root": str(tmp_path),
                "payload": {
                    "type": "AGENT_DONE",
                    "agent": "builder",
                    "run_id": run_id,
                    "summary": f"I printed {token}",
                    "error": f"PATHLY_RUN_TOKEN={token}",
                    "result": f"x{token}y",
                },
            },
        )
        assert r.status_code == 200
        eventlog.append_event(
            str(tmp_path / "pathly" / "features" / topic),
            {"type": "NOTE", "summary": f"direct {token}"},
            create_dir=False,
        )
        rows = get_run_log(conn, run_id)
        assert rows[-1]["stdout"] == (
            f"PATHLY_RUN_TOKEN: {REDACTED}\nraw {REDACTED} end"
        )
        assert rows[-1]["prompt_sent"] == "run with $PATHLY_RUN_TOKEN"
        stored = _stored_text(conn)
        assert any("I printed" in s for s in stored)
        assert all(token not in s for s in stored)
    finally:
        drop_run(run_id)
