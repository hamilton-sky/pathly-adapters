"""Every EXECUTED operator action is audit-logged as local-operator; nothing
else is (local-operator ticket 05): proposals, cancellations, stale cards and
read-only turns write no record.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from _operator_env import (
    BOARD,
    audit_rows,
    check,
    client,  # noqa: F401  (fixture)
    make_all_available,
    registry_run,
    run_card,
)


def test_an_executed_retry_writes_exactly_one_record(client, monkeypatch):  # noqa: F811
    import pathly_orchestrator.supervisor.api as api

    monkeypatch.setattr(
        api, "start_run", lambda **kw: SimpleNamespace(run_id="run-new-9")
    )
    with registry_run("run-aud-1", "error"):
        card = check(client, [{"name": "retry_run", "args": {"run_id": "run-aud-1"}}])[
            "cards"
        ][0]
        assert audit_rows() == []  # a proposal alone writes nothing
        assert run_card(client, card)["status"] == "done"
    rows = audit_rows()
    assert len(rows) == 1
    text = rows[0]["text"]
    assert text.startswith("⚡ HQ operator · retry_run ")
    assert (
        json.loads(text.split("retry_run ", 1)[1].split(" →")[0])["run_id"]
        == "run-aud-1"
    )
    assert "→ done: Restarted" in text and "confirmed in chat" in text
    assert rows[0]["type"] == "status"
    assert rows[0]["author_source"] == "system"  # server-written, never the model


def test_a_failed_execution_is_recorded_as_failed(client):  # noqa: F811
    with registry_run("run-aud-2", "running") as state:
        card = check(client, [{"name": "pause_run", "args": {"run_id": "run-aud-2"}}])[
            "cards"
        ][0]
        # Same fingerprint, but the run vanishes from the registry between
        # the resolve and the route call → the route answers not_active.
        from pathly_orchestrator.http_server.blueprints.hq import _action_exec

        real_call = _action_exec._call

        def call_after_vanish(method, path, body):
            from pathly_orchestrator.supervisor.registry import _lock, _registry

            with _lock:
                _registry.pop(state.topic, None)
            return real_call(method, path, body)

        _action_exec._call = call_after_vanish
        try:
            out = run_card(client, card)
        finally:
            _action_exec._call = real_call
    assert out["status"] == "failed" and "not active" in out["summary"]
    assert len(audit_rows()) == 1 and "→ failed:" in audit_rows()[0]["text"]


def test_cancel_stale_and_read_only_write_nothing(client):  # noqa: F811
    # Cancel = the card's Run is never clicked: check only.
    with registry_run("run-aud-3", "running") as state:
        card = check(client, [{"name": "stop_run", "args": {"run_id": "run-aud-3"}}])[
            "cards"
        ][0]
        state.status = "done"  # stale by the time Run is clicked
        assert run_card(client, card)["status"] == "stale"
    # A read-only turn (no actions) and an operator turn both build text only.
    for enabled in ([], ["pause_run"]):
        resp = client.post(
            "/hq/prompt",
            json={
                "message": "what needs attention?",
                "board": BOARD,
                "enabled_actions": enabled,
            },
        )
        assert resp.status_code == 200
    assert audit_rows() == []


def test_studio_run_actions_are_audited_on_report(client, tmp_path):  # noqa: F811
    make_all_available(client)
    target = {"artifact_id": "a1", "path": str(tmp_path / "x.md"), "style": "mermaid"}
    resp = client.post(
        "/hq/actions/report",
        json={
            "board": BOARD,
            "name": "diagram_artifact",
            "target": target,
            "ok": True,
            "summary": "Diagram started",
        },
    )
    assert resp.get_json()["ok"] is True
    (row,) = audit_rows()
    assert "diagram_artifact" in row["text"] and '"style": "mermaid"' in row["text"]
    assert str(tmp_path) not in row["text"]  # one line, no file paths or payloads
    # A server-run action can't be "reported" — /hq/actions/run audits those itself.
    bad = client.post(
        "/hq/actions/report",
        json={"board": BOARD, "name": "stop_run", "target": {}, "ok": True},
    )
    assert bad.status_code == 400
