"""Feature-decompose ladder (planner-hierarchy T5): route dispatch, goal-count gate, flow, skill.

The light-tier AGENT actually posting 2-5 type=goal cards is agent-compliance-dependent and not
unit-testable; these lock the DETERMINISTIC surface — the route's rigor dispatch fork, the
count_goals_for_feature gate, the feature-consultation flow shape, and that the terminal skill
composes and emits type=goal (not type=task).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

import pathly_data


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _clear_file_claims():
    from pathly_orchestrator.supervisor import file_claims

    file_claims._claims.clear()
    yield
    file_claims._claims.clear()


@pytest.fixture()
def client():
    from pathly_orchestrator.http_server import app

    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _flow() -> dict:
    p = (
        Path(pathly_data.__file__).parent
        / "core"
        / "flows"
        / "feature-consultation.flow.yaml"
    )
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _seed_goal(scope: str, deps=None, refs=None) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    gid = post_message(
        conn, board="feature", scope=scope, from_agent="planner", type="goal", text="G"
    )
    if deps or refs:
        conn.execute(
            "UPDATE comms_messages SET depends_on=?, context_refs=? WHERE id=?",
            (json.dumps(deps or []), json.dumps(refs or []), gid),
        )
        conn.commit()
    return gid


# ── (c) route dispatch per rigor ──────────────────────────────────────────────
def test_light_dispatch_uses_feature_decompose_skill(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        seen.update(skill=kw.get("skill"), agent=kw.get("agent"))
        return {"ok": True, "run_id": "r1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post(
        "/comms/features/decompose", json={"feature": "featdec-light", "rigor": "light"}
    )
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert seen["skill"] == "planning/feature-decompose"


def test_full_dispatch_uses_plan_skill(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        seen["skill"] = kw.get("skill")
        return {"ok": True, "run_id": "r1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post(
        "/comms/features/decompose", json={"feature": "featdec-full", "rigor": "full"}
    )
    assert r.status_code == 200
    assert seen["skill"] == "planning/plan"


def test_consultation_dispatch_starts_feature_consultation_flow(client, monkeypatch):
    import pathly_orchestrator.supervisor.api as _api

    seen: dict = {}

    class _FakeState:
        run_id = "cr1"

    def _fake_start(**kw):
        seen["flow"] = kw.get("flow")
        seen["topic"] = kw.get("topic")
        return _FakeState()

    monkeypatch.setattr(_api, "start_run", _fake_start)
    r = client.post(
        "/comms/features/decompose",
        json={"feature": "featdec-consult", "rigor": "consultation"},
    )
    assert r.status_code == 200 and r.get_json()["rigor"] == "consultation"
    assert seen["flow"] == "feature-consultation"
    assert seen["topic"] == "featdec-consult"


def test_invalid_rigor_rejected(client):
    r = client.post(
        "/comms/features/decompose", json={"feature": "x", "rigor": "bogus"}
    )
    assert r.status_code == 400 and r.get_json()["reason"] == "invalid_rigor"


def test_missing_feature_is_400_not_500(client):
    r = client.post("/comms/features/decompose", json={"rigor": "light"})
    assert r.status_code == 400


# ── (a)/(b) goal seeding + count contract ─────────────────────────────────────
def test_count_goals_for_feature_and_stored_deps_refs():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_counts import count_goals_for_feature

    scope = "featdec-count"
    _seed_goal(scope)
    g2 = _seed_goal(scope, deps=["dep-x"], refs=[{"artifact": "ARCHITECTURE.md"}])
    conn = get_db()
    assert count_goals_for_feature(conn, scope) == 2
    # (b) depends_on + context_refs round-trip on a posted goal.
    row = conn.execute(
        "SELECT depends_on, context_refs FROM comms_messages WHERE id=?", (g2,)
    ).fetchone()
    assert json.loads(row["depends_on"]) == ["dep-x"]
    assert json.loads(row["context_refs"]) == [{"artifact": "ARCHITECTURE.md"}]


# ── (d) goal-count gate on PLANNING ───────────────────────────────────────────
def test_goal_count_gate_routes_by_count(tmp_path):
    from pathly_orchestrator.fsm.engine_transitions import evaluate_transition_rules

    flow = _flow()
    _seed_goal("featdec-gate-lo")  # only 1 goal
    assert (
        evaluate_transition_rules(
            flow, "PLANNING", tmp_path, feature_scope="featdec-gate-lo"
        )
        == "NO_GOALS_SEEDED"
    )
    _seed_goal("featdec-gate-hi")
    _seed_goal("featdec-gate-hi")  # 2 goals
    assert (
        evaluate_transition_rules(
            flow, "PLANNING", tmp_path, feature_scope="featdec-gate-hi"
        )
        == "DONE"
    )


# ── (e) consultation flow shape ───────────────────────────────────────────────
def test_feature_consultation_flow_shape():
    flow = _flow()
    assert flow["flow"] == "feature-consultation"
    assert "PLANNING" in flow["states"]
    assert (
        "NO_GOALS_SEEDED" in flow["states"]
        and flow["transitions"]["NO_GOALS_SEEDED"] == []
    )
    # terminal stage emits GOALS (planning/feature-decompose), not planning/plan.
    assert flow["agent_map"]["PLANNING"] == "planning/feature-decompose"


def test_feature_decompose_skill_composes_and_emits_goal():
    from pathly_orchestrator.skills.compose import compose_skill

    body = compose_skill("planning/feature-decompose", "claude")
    assert len(body) > 500
    assert '"type": "goal"' in body  # posts GOAL cards
