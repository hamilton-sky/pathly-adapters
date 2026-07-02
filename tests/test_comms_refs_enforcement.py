"""Tests for CT3 — context_refs enforcement + coverage + unverified auto-derive.

T3c: GET /comms/goals/refs-coverage reports tasks-with-refs / total for a goal.
T3a: POST /comms/post of a ref-less task returns a non-blocking ref_warning; refs or an
     explicit no_refs reason suppress it.
T3b: retrieve_board_context labels the semantic channel "Auto-derived context (UNVERIFIED)"
     when the task has no curated refs — never "authoritative", never persisted.
"""

from __future__ import annotations

import json

import pytest


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _post(client, **fields):
    body = {"feature": "demo", "board": "feature", "scope": "demo"}
    body.update(fields)
    r = client.post("/comms/post", json=body)
    assert r.status_code == 200, r.data
    return json.loads(r.data)


# ── T3a ────────────────────────────────────────────────────────────────────
def test_t3a_ref_warning_on_refless_task(client):
    refless = _post(client, **{"from": "planner", "type": "task", "text": "no refs task"})
    assert "ref_warning" in refless

    with_refs = _post(
        client,
        **{
            "from": "planner",
            "type": "task",
            "text": "has refs",
            "context_refs": [{"artifact": "pathly/features/demo/X.md"}],
        },
    )
    assert "ref_warning" not in with_refs

    justified = _post(
        client,
        **{
            "from": "planner",
            "type": "task",
            "text": "first task",
            "no_refs": "fresh feature — nothing to reference yet",
        },
    )
    assert "ref_warning" not in justified


def test_t3a_no_warning_for_non_task(client):
    note = _post(client, **{"from": "planner", "type": "discovery", "text": "a note"})
    assert "ref_warning" not in note


# ── T3c ────────────────────────────────────────────────────────────────────
def test_t3c_goal_refs_coverage(client):
    goal = _post(client, **{"from": "human", "type": "goal", "text": "G"})["message_id"]
    for name in ("A", "B"):
        _post(
            client,
            **{
                "from": "planner",
                "type": "task",
                "text": f"task {name}",
                "goal_id": goal,
                "context_refs": [{"artifact": f"pathly/features/demo/{name}.md"}],
            },
        )
    _post(client, **{"from": "planner", "type": "task", "text": "task C", "goal_id": goal})

    r = client.get(f"/comms/goals/refs-coverage?goal_id={goal}")
    assert r.status_code == 200
    cov = json.loads(r.data)
    assert cov["total"] == 3
    assert cov["with_refs"] == 2
    assert cov["without_refs"] == 1
    assert cov["coverage_pct"] == 66.7


def test_t3c_requires_goal_id(client):
    assert client.get("/comms/goals/refs-coverage").status_code == 400


# ── T3b ────────────────────────────────────────────────────────────────────
def _stub_semantic(monkeypatch):
    import pathly_orchestrator.db.queries.comms as cq
    import pathly_orchestrator.runner.embeddings as emb

    monkeypatch.setattr(cq, "get_pending_decisions", lambda *a, **k: [])
    monkeypatch.setattr(cq, "get_active_escalations", lambda *a, **k: [])
    monkeypatch.setattr(emb, "embed", lambda t: [0.0] * 384)
    monkeypatch.setattr(
        cq,
        "search_by_hybrid",
        lambda conn, text, ev, boards, scopes, k: [
            {
                "id": "sg",
                "text": "semantic guess row",
                "from_agent": "a",
                "to_agent": "*",
                "_distance": 0.30,
            }
        ],
    )


def test_t3b_unverified_header_when_task_has_no_refs(client, monkeypatch):
    tid = _post(client, **{"from": "planner", "type": "task", "text": "do X"})["message_id"]
    _stub_semantic(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    block = cc.retrieve_board_context(
        "demo",
        "C:/p",
        "do X",
        board_scope={"feature": True, "project": False, "global": False},
        task_id=tid,
    )
    assert "Auto-derived context (UNVERIFIED" in block
    assert "semantic guess row" in block
    # The normal "possibly relevant" header must NOT be used for a ref-less task.
    assert "Context (possibly relevant" not in block


def test_t3b_normal_header_when_no_task_id(monkeypatch):
    _stub_semantic(monkeypatch)
    import pathly_orchestrator.runner.comms_context as cc

    block = cc.retrieve_board_context(
        "demo",
        "C:/p",
        "do X",
        board_scope={"feature": True, "project": False, "global": False},
    )
    assert "Context (possibly relevant" in block
    assert "Auto-derived context (UNVERIFIED" not in block
