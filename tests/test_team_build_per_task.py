"""team-build per-task loop + goal-DAG completeness gate.

The `team` executor must build→review EACH task (loop BUILDING↔REVIEWING while the goal has
buildable tasks) and only integration-test once the whole DAG is drained — and must never reach
RETRO/DONE with unfinished or failed tasks. Locks that routing on the shipped flow + the two
new count helpers + the require_tasks_done gate.
"""

import json
from pathlib import Path

import pytest
import yaml

import pathly_data
from pathly_orchestrator.fsm.engine_actions import run_gates
from pathly_orchestrator.fsm.engine_transitions import evaluate_transition_rules


def _team_build_flow() -> dict:
    p = Path(pathly_data.__file__).parent / "core" / "flows" / "team-build.flow.yaml"
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _no_async_embed(monkeypatch):
    import pathly_orchestrator.runner.embeddings as _emb

    monkeypatch.setattr(_emb, "embed_async", lambda *a, **k: None)


def _seed_goal(scope: str) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    return post_message(
        get_db(), board="feature", scope=scope, from_agent="architect", type="goal", text="g"
    )


def _seed_task(scope: str, gid: str, status: str, deps=None) -> str:
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import post_message

    conn = get_db()
    tid = post_message(
        conn, board="feature", scope=scope, from_agent="planner", type="task", text="t", goal_id=gid
    )
    conn.execute(
        "UPDATE comms_messages SET task_status=?, depends_on=? WHERE id=?",
        (status, json.dumps(deps or []), tid),
    )
    conn.commit()
    return tid


# ── count helpers ─────────────────────────────────────────────────────────────
def test_counts_ready_and_incomplete():
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms_tasks import (
        count_incomplete_tasks_for_goal,
        count_ready_tasks_for_goal,
    )

    gid = _seed_goal("ptl-counts")
    t1 = _seed_task("ptl-counts", gid, "done")
    _seed_task("ptl-counts", gid, "pending", deps=[t1])         # ready — dep is done
    _seed_task("ptl-counts", gid, "pending", deps=["missing"])  # blocked — dep not done
    conn = get_db()
    assert count_ready_tasks_for_goal(conn, gid) == 1
    assert count_incomplete_tasks_for_goal(conn, gid) == 2  # both pending rows


# ── per-task loop routing (REVIEWING) ─────────────────────────────────────────
def test_reviewing_loops_to_building_while_ready(tmp_path):
    gid = _seed_goal("ptl-loop")
    t1 = _seed_task("ptl-loop", gid, "done")
    _seed_task("ptl-loop", gid, "pending", deps=[t1])  # one buildable task remains
    assert (
        evaluate_transition_rules(_team_build_flow(), "REVIEWING", tmp_path, goal_id=gid)
        == "BUILDING"
    )


def test_reviewing_advances_to_testing_when_dag_drained(tmp_path):
    gid = _seed_goal("ptl-drained")
    _seed_task("ptl-drained", gid, "done")
    _seed_task("ptl-drained", gid, "done")
    assert (
        evaluate_transition_rules(_team_build_flow(), "REVIEWING", tmp_path, goal_id=gid)
        == "TESTING"
    )


def test_review_failures_wins_over_loop(tmp_path):
    """on_artifact REVIEW_FAILURES.md must still take precedence over the ready-loop."""
    gid = _seed_goal("ptl-revfail")
    t1 = _seed_task("ptl-revfail", gid, "done")
    _seed_task("ptl-revfail", gid, "pending", deps=[t1])
    (tmp_path / "REVIEW_FAILURES.md").write_text("x", encoding="utf-8")
    assert (
        evaluate_transition_rules(_team_build_flow(), "REVIEWING", tmp_path, goal_id=gid)
        == "BUILDING"
    )


def test_non_goal_run_keeps_single_pass(tmp_path):
    """No goal_id → on_board_count is skipped → REVIEWING defaults to TESTING (legacy behavior)."""
    assert (
        evaluate_transition_rules(_team_build_flow(), "REVIEWING", tmp_path, goal_id=None)
        == "TESTING"
    )


# ── completeness gate (require_tasks_done) ────────────────────────────────────
_GATE_FLOW = {
    "gates": {"REVIEWING->TESTING": [{"type": "require_tasks_done", "on_fail": "INCOMPLETE_TASKS.md"}]}
}


def test_require_tasks_done_blocks_when_incomplete(tmp_path):
    gid = _seed_goal("ptl-gate-block")
    _seed_task("ptl-gate-block", gid, "done")
    _seed_task("ptl-gate-block", gid, "pending")  # not done
    res = run_gates(_GATE_FLOW, "REVIEWING", "TESTING", tmp_path, "t", 0, goal_id=gid)
    assert res is not None and res["feedback_file"] == "INCOMPLETE_TASKS.md"
    assert (tmp_path / "feedback" / "INCOMPLETE_TASKS.md").exists()


def test_require_tasks_done_passes_when_all_done(tmp_path):
    gid = _seed_goal("ptl-gate-pass")
    _seed_task("ptl-gate-pass", gid, "done")
    _seed_task("ptl-gate-pass", gid, "done")
    assert run_gates(_GATE_FLOW, "REVIEWING", "TESTING", tmp_path, "t", 0, goal_id=gid) is None


def test_require_tasks_done_noop_without_goal(tmp_path):
    """Non-goal feature runs (goal_id None) have no DAG — the gate is a no-op."""
    assert run_gates(_GATE_FLOW, "REVIEWING", "TESTING", tmp_path, "t", 0, goal_id=None) is None


# ── structural (shipped flow) ─────────────────────────────────────────────────
def test_shipped_flow_wires_loop_and_gate():
    flow = _team_build_flow()
    rev = flow["transition_rules"]["REVIEWING"]
    assert rev["on_board_count"] == {"metric": "ready", "op": "gt", "compare_to": 0, "next": "BUILDING"}
    assert rev["default"] == "TESTING"
    gate_types = [g["type"] for g in flow["gates"]["REVIEWING->TESTING"]]
    assert "require_tasks_done" in gate_types
    assert flow["feedback_routing"]["INCOMPLETE_TASKS"] == "builder"
