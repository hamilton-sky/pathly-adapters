"""Project-decompose ladder (planner-hierarchy G2): route dispatch, feature-count gate, flow, skill.

Mirror of test_feature_decompose.py one altitude up (project → sibling FEATURES instead of
feature → sibling goals). The light-tier AGENT actually posting 2-5 type=feature cards +
scaffolding pathly/features/<slug>/SPEC.md is agent-compliance-dependent and not unit-testable;
these lock the DETERMINISTIC surface — the route's rigor dispatch fork, the
count_features_for_project gate, the project-consultation flow shape, and that the terminal skill
composes and emits type=feature (not type=goal).

The project-board scope is the NORMALIZED project_root path (Option 1); an explicit ``project``
field overrides it, and literal "project" is the no-root fallback.
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
    p = Path(pathly_data.__file__).parent / "core" / "flows" / "project-consultation.flow.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def _seed_feature(scope: str, deps=None, refs=None) -> str:
    """Post a type=feature card on the PROJECT board for a project scope."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    fid = post_message(conn, board="project", scope=scope, from_agent="planner", type="feature", text="F")
    if deps or refs:
        conn.execute(
            "UPDATE comms_messages SET depends_on=?, context_refs=? WHERE id=?",
            (json.dumps(deps or []), json.dumps(refs or []), fid),
        )
        conn.commit()
    return fid


# ── (c) route dispatch per rigor ──────────────────────────────────────────────
def test_light_dispatch_uses_project_decompose_skill(client, monkeypatch):
    import pathly_orchestrator.supervisor.board_run as _br

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        seen.update(board=board, skill=kw.get("skill"), agent=kw.get("agent"))
        return {"ok": True, "run_id": "r1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post("/comms/project/decompose", json={"project": "projdec-light", "rigor": "light"})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    assert seen["skill"] == "planning/project-decompose"
    assert seen["board"] == "project"


def test_full_dispatch_uses_project_decompose_skill(client, monkeypatch):
    # Unlike the feature route (full → planning/plan), project 'full' also uses
    # planning/project-decompose: it is the only skill that emits type=feature, so
    # routing 'full' to planning/plan would emit tasks and trip the >=2-features gate.
    import pathly_orchestrator.supervisor.board_run as _br

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        seen["skill"] = kw.get("skill")
        return {"ok": True, "run_id": "r1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post("/comms/project/decompose", json={"project": "projdec-full", "rigor": "full"})
    assert r.status_code == 200
    assert seen["skill"] == "planning/project-decompose"


def test_consultation_dispatch_starts_project_consultation_flow(client, monkeypatch):
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
        "/comms/project/decompose", json={"project": "projdec-consult", "rigor": "consultation"}
    )
    assert r.status_code == 200 and r.get_json()["rigor"] == "consultation"
    assert seen["flow"] == "project-consultation"
    # topic = the project scope (Option 1: normalized project_root, or the explicit override).
    assert seen["topic"] == "projdec-consult"


def test_scope_defaults_to_normalized_project_root(client, monkeypatch):
    """No explicit `project` → scope derives from the normalized project_root path."""
    import pathly_orchestrator.supervisor.board_run as _br

    seen: dict = {}

    def _fake(board, scope, mode, **kw):
        seen["scope"] = scope
        return {"ok": True, "run_id": "r1"}

    monkeypatch.setattr(_br, "start_board_run", _fake)
    r = client.post(
        "/comms/project/decompose",
        json={"project_root": "C:\\Users\\Yafit\\demo\\", "rigor": "light"},
    )
    assert r.status_code == 200
    assert seen["scope"] == "C:/Users/Yafit/demo"  # backslashes normalized, trailing slash stripped


def test_invalid_rigor_rejected(client):
    r = client.post("/comms/project/decompose", json={"project": "x", "rigor": "bogus"})
    assert r.status_code == 400 and r.get_json()["reason"] == "invalid_rigor"


def test_missing_body_is_400_not_500(client):
    r = client.post("/comms/project/decompose", json={})
    assert r.status_code == 400 and r.get_json()["reason"] == "missing_body"


# ── (a)/(b) feature seeding + count contract ──────────────────────────────────
def test_count_features_for_project_and_stored_deps_refs():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_counts import count_features_for_project

    scope = "projdec-count"
    _seed_feature(scope)
    f2 = _seed_feature(scope, deps=["dep-x"], refs=[{"artifact": "pathly/project/ARCHITECTURE.md"}])
    conn = get_db()
    assert count_features_for_project(conn, scope) == 2
    # (b) depends_on + context_refs round-trip on a posted feature.
    row = conn.execute("SELECT depends_on, context_refs FROM comms_messages WHERE id=?", (f2,)).fetchone()
    assert json.loads(row["depends_on"]) == ["dep-x"]
    assert json.loads(row["context_refs"]) == [{"artifact": "pathly/project/ARCHITECTURE.md"}]


def test_count_features_is_project_board_scoped():
    """count_features_for_project only counts board='project' type='feature' — a same-scope
    feature card on the FEATURE board must not inflate the project count."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message
    from pathly_orchestrator.db.queries.comms_counts import count_features_for_project

    scope = "projdec-boardscoped"
    conn = get_db()
    _seed_feature(scope)  # board='project'
    post_message(conn, board="feature", scope=scope, from_agent="planner", type="feature", text="wrong board")
    assert count_features_for_project(conn, scope) == 1


# ── (d) feature-count gate on PLANNING ────────────────────────────────────────
def test_feature_count_gate_routes_by_count(tmp_path):
    from pathly_orchestrator.fsm.engine_transitions import evaluate_transition_rules

    flow = _flow()
    _seed_feature("projdec-gate-lo")  # only 1 feature
    assert (
        evaluate_transition_rules(flow, "PLANNING", tmp_path, feature_scope="projdec-gate-lo")
        == "NO_FEATURES_SEEDED"
    )
    _seed_feature("projdec-gate-hi")
    _seed_feature("projdec-gate-hi")  # 2 features
    assert (
        evaluate_transition_rules(flow, "PLANNING", tmp_path, feature_scope="projdec-gate-hi")
        == "DONE"
    )


# ── (e) consultation flow shape ───────────────────────────────────────────────
def test_project_consultation_flow_shape():
    flow = _flow()
    assert flow["flow"] == "project-consultation"
    assert "PLANNING" in flow["states"]
    assert "NO_FEATURES_SEEDED" in flow["states"] and flow["transitions"]["NO_FEATURES_SEEDED"] == []
    # terminal stage emits FEATURES (planning/project-decompose), not planning/plan.
    assert flow["agent_map"]["PLANNING"] == "planning/project-decompose"
    # storage is pinned (NOT pathly/{topic}/) because the topic is a path-like scope.
    assert flow["storage_path"] == "pathly/project/"


def test_project_decompose_skill_composes_and_emits_feature():
    from pathly_orchestrator.skills.compose import compose_skill

    body = compose_skill("planning/project-decompose", "claude")
    assert len(body) > 500
    assert '"type": "feature"' in body  # posts FEATURE cards
