"""`supervisor/task_proof.wrap` on its own (build-proof 05).

The drain-level behaviour is in `test_task_proof.py`. These cover what a drain cannot show: a
run id that is not a DAG task passes straight through, the terminal spawn is resolved when the
wrapper is called, a spawn that raises or reports failure is returned as is, windows that overlap
leave each other's declared paths out of the diff, and the error's shape. Setup is in
`task_proof_support`.
"""

from __future__ import annotations

import pytest
from task_proof_support import (
    RED_TEXT,
    SKIPPED_TEST,
    State,
    add_task,
    make_repo,
    proofs,
    set_app_setting,
    set_text,
    write,
)

from tests._python import python_command


@pytest.fixture(autouse=True)
def _code_intel_off(_isolate_db):
    set_app_setting("code_context.backend", "off")


def _run_id(task_id: str) -> str:
    return "sched-%s#1" % task_id


def test_a_run_id_that_is_not_a_dag_task_passes_straight_through(tmp_path):
    from pathly_orchestrator.supervisor import task_proof

    state = State(make_repo(tmp_path))
    calls: list = []

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        calls.append(run_id)
        return {"outcome": "failed", "error": "kept"}

    result = task_proof.wrap(spawn)(state, "p", "claude", "m", "board-run-uuid", None)

    assert result == {"outcome": "failed", "error": "kept"}
    assert calls == ["board-run-uuid"]
    assert proofs(state) == []


def test_without_a_spawn_it_resolves_the_terminal_spawn_when_called(
    tmp_path, monkeypatch
):
    import pathly_orchestrator.supervisor as sup
    from pathly_orchestrator.supervisor import task_proof

    wrapped = task_proof.wrap(None)
    calls: list = []

    def fake(state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        calls.append(run_id)
        return {"outcome": "success"}

    monkeypatch.setattr(sup, "_run_stage_via_terminal", fake)

    state = State(make_repo(tmp_path))
    assert wrapped(state, "p", "c", "m", "run-1", None) == {"outcome": "success"}
    assert calls == ["run-1"]


def test_a_spawn_that_raises_or_reports_failure_is_returned_as_it_is(tmp_path):
    from pathly_orchestrator.supervisor import task_proof

    state = State(make_repo(tmp_path))
    tid = add_task(RED_TEXT)
    failed = {"outcome": "failed", "error": "it broke", "cost_usd": 0.1}

    def boom(state, instructions, adapter, model, run_id, broadcast_fn):
        raise RuntimeError("agent crashed")

    def reports_failure(state, instructions, adapter, model, run_id, broadcast_fn):
        return failed

    with pytest.raises(RuntimeError, match="agent crashed"):
        task_proof.wrap(boom)(state, "p", "c", "m", _run_id(tid), None)
    assert task_proof._IN_FLIGHT == {}

    wrapped = task_proof.wrap(reports_failure)
    assert wrapped(state, "p", "c", "m", _run_id(tid), None) == failed
    assert task_proof._IN_FLIGHT == {}
    assert proofs(state) == []


def _overlapping(tmp_path, a_files, b_files):
    """Task A's spawn runs task B's wrapped spawn inside it: their windows overlap."""
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import claim_task
    from pathly_orchestrator.supervisor import task_proof

    repo = make_repo(tmp_path)
    state = State(repo)
    a = add_task("Task a.", files=a_files)
    b = add_task("Task b.", files=b_files)
    for tid in (a, b):
        assert claim_task(get_db(), tid, run_id=_run_id(tid))
    results: dict = {}

    def spawn_b(state, instructions, adapter, model, run_id, broadcast_fn):
        write("tests/test_sample.py", SKIPPED_TEST)(repo)
        return {"outcome": "success"}

    def spawn_a(state, instructions, adapter, model, run_id, broadcast_fn):
        write("src/a.py", "a = 1\n")(repo)
        wrapped_b = task_proof.wrap(spawn_b)
        results["b"] = wrapped_b(state, "p", "c", "m", _run_id(b), None)
        return {"outcome": "success"}

    results["a"] = task_proof.wrap(spawn_a)(state, "p", "c", "m", _run_id(a), None)
    assert task_proof._IN_FLIGHT == {}
    return results


def test_a_path_an_overlapping_task_declared_is_left_out_of_the_diff(tmp_path):
    results = _overlapping(tmp_path, ["src/a.py"], ["tests/"])

    assert results["a"] == {"outcome": "success"}
    assert results["b"]["outcome"] == "failed"
    assert "skip: tests/test_sample.py" in results["b"]["error"]


def test_a_path_nobody_declared_counts_against_every_overlapping_task(tmp_path):
    results = _overlapping(tmp_path, ["src/a.py"], None)

    assert results["a"]["outcome"] == "failed"
    assert "skip: tests/test_sample.py" in results["a"]["error"]
    assert results["b"]["outcome"] == "failed"


def test_the_error_names_each_failing_part_and_stays_within_4000_characters(tmp_path):
    from pathly_orchestrator.db.connection import get_db
    from pathly_orchestrator.db.queries.comms import claim_task
    from pathly_orchestrator.supervisor import task_proof

    repo = make_repo(tmp_path)
    state = State(repo)
    noisy = "import sys; print('x' * 12000); sys.exit(4)"
    tid = add_task(f"Greet.\n\n```check\n$ {python_command(noisy)}\n```\n")
    assert claim_task(get_db(), tid, run_id=_run_id(tid))

    def spawn(state, instructions, adapter, model, run_id, broadcast_fn):
        write("tests/test_sample.py", SKIPPED_TEST)(repo)
        set_text(tid, "Something else.")
        return {"outcome": "success", "cost_usd": 0.5}

    result = task_proof.wrap(spawn)(state, "p", "c", "m", _run_id(tid), None)

    assert result["outcome"] == "failed" and result["cost_usd"] == 0.5
    error = result["error"]
    assert 1000 < len(error) <= 4000
    assert error.index("Floor guard") < error.index("Task text") < error.index("Checks")
    assert "skip: tests/test_sample.py" in error and "task-edit" in error
    assert "got: exit 4" in error
    [proof] = proofs(state)
    assert (proof["checks"], proof["floor"]) == ("failed", "failed")
