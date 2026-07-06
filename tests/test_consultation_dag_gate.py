"""The consultation decompose must FAIL LOUDLY when the planner seeds no DAG.

Posting the task DAG is agent-compliance-dependent (a board POST the planner may skip).
If the planner produces plan docs but 0 tasks, the PLANNING stage must route to a distinct
terminal (NO_DAG_SEEDED) — not silently re-loop PLANNING or falsely complete. The gate is
goal-scoped + fail-safe; this locks the loud-failure routing on the shipped flow.
"""

from pathlib import Path

import pytest
import yaml

import pathly_data
from pathly_orchestrator.fsm.engine_transitions import evaluate_transition_rules


def _consultation_flow() -> dict:
    p = Path(pathly_data.__file__).parent / "core" / "flows" / "consultation.flow.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _seed_goal(scope: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    return post_message(
        conn, board="feature", scope=scope, from_agent="architect", type="goal", text="g"
    )


def test_flow_declares_no_dag_seeded_terminal():
    flow = _consultation_flow()
    assert "NO_DAG_SEEDED" in flow["states"]
    assert flow["transitions"].get("NO_DAG_SEEDED") == []
    assert flow["transition_rules"]["PLANNING"]["default"] == "NO_DAG_SEEDED"


def test_planning_routes_to_no_dag_seeded_when_zero_tasks(tmp_path):
    gid = _seed_goal("dag-loud-1")
    flow = _consultation_flow()
    # planner ran but seeded 0 tasks -> loud terminal, NOT PLANNING (loop) / DONE (false success)
    assert evaluate_transition_rules(flow, "PLANNING", tmp_path, goal_id=gid) == "NO_DAG_SEEDED"


def test_planning_completes_when_tasks_seeded(tmp_path):
    gid = _seed_goal("dag-loud-2")
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    tid = post_message(
        conn, board="feature", scope="dag-loud-2", from_agent="planner",
        type="task", text="t", goal_id=gid,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (tid,))
    conn.commit()
    flow = _consultation_flow()
    assert evaluate_transition_rules(flow, "PLANNING", tmp_path, goal_id=gid) == "DONE"
