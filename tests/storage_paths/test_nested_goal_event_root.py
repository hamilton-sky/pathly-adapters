"""Readers of a nested goal run's event log key it the way `eventlog.append_event` writes it.

A goal run lives at `<root>/pathly/features/<f>/goals/<slug>`. `append_event` keys its events
by `eventlog._project_root_of` (the dir above `pathly/`), but four readers derived the root as
`storage.parent.parent.parent` — `<root>/pathly/features` for this depth — and so read nothing:

* `runner.read_last_agent_done` (the PTY result's AGENT_DONE summary and outcome),
* `runner._patch_last_agent_done` (the BILLING_UPDATE's agent/conversation),
* `supervisor.terminal_reconcile._agent_done_watcher` (early advance),
* `fsm.route_feedback`'s `feedback_items` sync.

The watcher also matched ANY AGENT_DONE for the slug, so in a drain whose tasks share the
goal's storage one task's report could end another task's spawn. It now takes only its own
run's AGENT_DONE (or an unstamped one, from an agent that reports no run_id).
"""

from __future__ import annotations

import threading
from pathlib import Path

from pathly_orchestrator import eventlog


def _goal_storage(root: Path) -> Path:
    storage = root / "pathly" / "features" / "feat" / "goals" / "slug"
    storage.mkdir(parents=True)
    return storage


def _agent_done(storage: Path, **fields) -> None:
    eventlog.append_event(
        str(storage), {"type": "AGENT_DONE", "agent": "builder", **fields}
    )


def test_read_last_agent_done_finds_a_nested_goal_runs_report(tmp_path):
    from pathly_orchestrator.runner import read_last_agent_done

    storage = _goal_storage(tmp_path)
    _agent_done(storage, summary="built it", outcome="failed", run_id="r-1")

    last = read_last_agent_done(storage)

    assert last is not None, "the PTY result would lose the summary and the outcome"
    assert (last["summary"], last["outcome"]) == ("built it", "failed")


def test_billing_update_names_the_nested_runs_agent(tmp_path):
    from pathly_orchestrator.runner import _patch_last_agent_done

    storage = _goal_storage(tmp_path)
    _agent_done(storage, conversation=4, run_id="r-1")

    _patch_last_agent_done(storage, 0.5, 10, 20, 3, run_id="r-1")

    [billing] = [
        e for e in eventlog.read_events(str(storage)) if e["type"] == "BILLING_UPDATE"
    ]
    assert (billing["agent"], billing["conversation"]) == ("builder", 4)


def _watch(storage: Path, run_id: str):
    from pathly_orchestrator.supervisor.registry import TerminalRun
    from pathly_orchestrator.supervisor.terminal_reconcile import _agent_done_watcher

    run = TerminalRun(run_id=run_id)
    t = threading.Thread(
        target=_agent_done_watcher, args=(run, storage, storage.name, 0), daemon=True
    )
    t.start()
    return run, t


def _wait_done(run, seconds: float) -> bool:
    with run._cond:
        return run._cond.wait_for(lambda: run.agent_done, timeout=seconds)


def test_the_watcher_sees_its_own_report_under_a_nested_goal(tmp_path):
    storage = _goal_storage(tmp_path)
    run, t = _watch(storage, "sched-a#1")
    _agent_done(storage, run_id="sched-a#1")
    try:
        assert _wait_done(run, 5.0), "early advance never fired for a goal run"
    finally:
        run.request_stop_watcher()
        t.join(2)


def test_the_watcher_ignores_another_runs_report(tmp_path):
    storage = _goal_storage(tmp_path)
    run, t = _watch(storage, "sched-a#1")
    _agent_done(storage, run_id="sched-b#1")
    try:
        assert not _wait_done(run, 0.8), "task b's report ended task a's spawn"
        _agent_done(storage, run_id="sched-a#1")
        assert _wait_done(run, 5.0)
    finally:
        run.request_stop_watcher()
        t.join(2)


def test_the_watcher_still_takes_a_report_with_no_run_id(tmp_path):
    """An agent whose report carries no run_id (an older skill) still advances early."""
    storage = _goal_storage(tmp_path)
    run, t = _watch(storage, "stage-1")
    _agent_done(storage, summary="done")
    try:
        assert _wait_done(run, 5.0)
    finally:
        run.request_stop_watcher()
        t.join(2)


def test_route_feedback_records_a_nested_runs_feedback_under_the_project_root(tmp_path):
    from pathly_orchestrator.db import get_db, read_feedback_items
    from pathly_orchestrator.fsm import route_feedback

    storage = _goal_storage(tmp_path)
    (storage / "feedback").mkdir()
    (storage / "feedback" / "BUILD_FAILURES.md").write_text("red\n", encoding="utf-8")

    route_feedback({"feedback_routing": {"BUILD_FAILURES": "builder"}}, storage)

    items = read_feedback_items(get_db(), tmp_path.as_posix(), "slug")
    assert [i["filename"] for i in items] == ["BUILD_FAILURES.md"]
