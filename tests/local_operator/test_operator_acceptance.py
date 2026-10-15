"""Acceptance for local-operator (ticket 06): propose → confirm → exactly one action.

The model is a scripted stub (no real model): it reads the function definitions
the operator turn offers and "calls" one, exactly as node-llama-cpp hands a
call to Studio's record-only handler. The rest is the real server path Studio
drives: POST /hq/prompt → /hq/actions/check → (the Run click) /hq/actions/run.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from _operator_env import (
    BOARD,
    audit_rows,
    client,  # noqa: F401  (fixture)
    registry_run,
)

RUN_ID = "run-tests-failed-1"
ENABLED = ["pause_run", "resume_run", "retry_run", "stop_run", "post_note"]


def _operator_turn(client, message: str) -> dict:  # noqa: F811
    resp = client.post(
        "/hq/prompt",
        json={
            "message": message,
            "board": BOARD,
            "project_root": "/proj",
            "enabled_actions": ENABLED,
        },
    )
    assert resp.status_code == 200
    return resp.get_json()


def _stub_model(turn: dict) -> list[dict]:
    """Rerun the failed stage → the retry function, with the run id from the packet."""
    offered = {t["name"] for t in turn["tools"]}
    assert "retry_run" in offered
    return [{"name": "retry_run", "args": {"run_id": RUN_ID}}]


def _propose(client, message: str) -> dict:  # noqa: F811
    turn = _operator_turn(client, message)
    proposals = _stub_model(turn)
    out = client.post(
        "/hq/actions/check",
        json={
            "board": BOARD,
            "project_root": "/proj",
            "enabled_actions": turn["actions"],
            "proposals": proposals,
        },
    ).get_json()
    (card,) = out["cards"]
    return card


@pytest.fixture()
def retry_calls(monkeypatch):
    import pathly_orchestrator.supervisor.api as api

    calls: list[dict] = []

    def fake_start_run(**kw):
        calls.append(kw)
        return SimpleNamespace(run_id="run-tests-retry-2")

    monkeypatch.setattr(api, "start_run", fake_start_run)
    return calls


def test_rerun_failed_stage_is_proposed_then_runs_exactly_once(
    client, retry_calls  # noqa: F811
):
    with registry_run(RUN_ID, "error", flow="team-build"):
        card = _propose(client, "rerun the failed test stage")
        assert card["name"] == "retry_run" and card["status"] == "proposed"
        assert card["title"].startswith(f"Retry run {RUN_ID[:12]}")
        assert retry_calls == [] and audit_rows() == []  # proposing ran nothing

        out = client.post(
            "/hq/actions/run",
            json={
                "board": BOARD,
                "project_root": "/proj",
                "name": card["name"],
                "args": card["args"],
                "fingerprint": card["fingerprint"],
            },
        ).get_json()
    assert out["status"] == "done"
    assert len(retry_calls) == 1  # exactly one retry API call
    rows = audit_rows()
    assert len(rows) == 1 and "retry_run" in rows[0]["text"]


def test_without_the_click_nothing_runs(client, retry_calls):  # noqa: F811
    with registry_run(RUN_ID, "error", flow="team-build"):
        _propose(client, "rerun the failed test stage")  # proposed, then cancelled
    assert retry_calls == [] and audit_rows() == []


def test_the_model_is_offered_only_enabled_actions(client):  # noqa: F811
    turn = _operator_turn(client, "rerun the failed test stage")
    names = {t["name"] for t in turn["tools"]}
    assert names == set(ENABLED)
    for forbidden in (
        "answer_question",
        "post_directive",
        "update_settings",
        "run_shell",
    ):
        assert forbidden not in names
    assert not {"run_goal", "plan_goal"} & names  # catalog actions Settings left off
