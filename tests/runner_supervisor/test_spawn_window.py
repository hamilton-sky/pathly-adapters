"""supervisor/spawn_window.py — a ``SPAWN_WINDOW`` event per single-path stage spawn (build-proof 04).

The floor, scope and reviewer gates must tell who wrote a file, so every single-path spawn of a
flow that has one of those gates records the working tree before and after it, with its role.
Real ``git init`` repos under ``tmp_path`` and a fake spawn that edits a file: the event's whole
value is the two tree ids git built around the spawn, which a mock cannot show.
"""

from __future__ import annotations

import copy
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from pathly_orchestrator import eventlog
from pathly_orchestrator.proof import tree
from pathly_orchestrator.supervisor import fan_out, spawn_window

FLOOR_FLOW = {
    "gates": {
        "BUILDING->REVIEWING": [{"type": "floor_gate", "on_fail": "FLOOR_FAILURES.md"}]
    }
}


def _git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    )
    return done.stdout.strip()


def _write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "test")
    _write(root, "src/app.py", "def add(a, b):\n    return a + b\n")
    _write(root, "pathly/features/demo/IMPLEMENTATION_PLAN.md", "# Plan\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "initial")
    return root


def _storage(root: Path) -> Path:
    return root / "pathly" / "features" / "demo"


def _state(root: Path, *, storage: str | None = None, current_state="BUILDING"):
    return SimpleNamespace(
        project_root=str(root),
        topic="demo",
        storage_path=str(_storage(root)) if storage is None else storage,
        current_state=current_state,
    )


def _windows(storage: Path) -> list[dict]:
    return [
        event
        for event in eventlog.read_events(str(storage))
        if event.get("type") == "SPAWN_WINDOW"
    ]


def _editing_spawn(root: Path, calls: list, result=None):
    """A spawn that edits ``src/app.py`` and returns ``result`` (one object, checked by identity)."""
    result = {"ok": True, "cost_usd": 0.25} if result is None else result

    def spawn():
        calls.append(1)
        _write(root, "src/app.py", "def add(a, b):\n    return b + a\n")
        return result

    return spawn, result


# ── wants_windows ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("gate", ["floor_gate", "scope_gate", "reviewer_unchanged"])
@pytest.mark.parametrize("transition", ["BUILDING->REVIEWING", "->DONE"])
def test_wants_windows_for_each_gate_that_reads_them(gate, transition):
    flow = {
        "gates": {
            "TESTING->RETRO": [{"type": "command_gate", "command_key": "test"}],
            transition: [{"type": "require_tasks_done"}, {"type": gate}],
        }
    }
    assert spawn_window.wants_windows(flow) is True


@pytest.mark.parametrize(
    "flow",
    [
        None,
        {},
        {"gates": {}},
        {"gates": {"BUILDING->REVIEWING": [{"type": "command_gate"}]}},
        {"gates": {"BUILDING->REVIEWING": None}},
        {"scope_gate": {"exempt_prefixes": []}},
    ],
)
def test_no_window_gate_means_no_windows(flow):
    assert spawn_window.wants_windows(flow) is False


# ── observe ──────────────────────────────────────────────────────────────────


def test_observe_writes_one_window_with_the_role_and_two_trees(repo):
    calls: list = []
    spawn, expected = _editing_spawn(repo, calls)

    result = spawn_window.observe(
        _state(repo), FLOOR_FLOW, "builder", "demo-1-100", spawn
    )

    assert result is expected
    assert calls == [1]
    windows = _windows(_storage(repo))
    assert len(windows) == 1
    window = windows[0]
    assert window["role"] == "builder"
    assert window["run_id"] == "demo-1-100"
    assert window["state"] == "BUILDING"
    assert window["before"] and window["after"]
    assert window["before"] != window["after"]
    assert tree.changes(repo, window["before"], window["after"]) == [
        ("M", "src/app.py")
    ]
    head = _git(repo, "rev-parse", "HEAD")
    assert window["head_before"] == head
    assert window["head_after"] == head


def test_head_after_records_a_commit_the_spawn_made(repo):
    head_before = _git(repo, "rev-parse", "HEAD")

    def spawn():
        _write(repo, "src/app.py", "x = 1\n")
        _git(repo, "commit", "-q", "-am", "agent commit")
        return {"ok": True}

    spawn_window.observe(_state(repo), FLOOR_FLOW, "reviewer", "demo-2-200", spawn)

    (window,) = _windows(_storage(repo))
    assert window["role"] == "reviewer"
    assert window["head_before"] == head_before
    assert window["head_after"] == _git(repo, "rev-parse", "HEAD")
    assert window["head_after"] != head_before


def test_a_flow_without_a_window_gate_writes_none_and_takes_no_snapshot(
    repo, monkeypatch
):
    snapshots: list = []
    real_snapshot = tree.snapshot

    def counting_snapshot(root):
        snapshots.append(root)
        return real_snapshot(root)

    monkeypatch.setattr(tree, "snapshot", counting_snapshot)
    calls: list = []
    spawn, expected = _editing_spawn(repo, calls)
    flow = {"gates": {"BUILDING->REVIEWING": [{"type": "command_gate"}]}}

    result = spawn_window.observe(_state(repo), flow, "builder", "demo-1-1", spawn)

    assert result is expected
    assert calls == [1]
    assert snapshots == []
    assert _windows(_storage(repo)) == []


def test_a_spawn_that_raises_writes_none_and_re_raises(repo):
    def spawn():
        _write(repo, "src/app.py", "half done\n")
        raise RuntimeError("terminal_result_timeout: no result")

    with pytest.raises(RuntimeError, match="terminal_result_timeout"):
        spawn_window.observe(_state(repo), FLOOR_FLOW, "builder", "demo-1-1", spawn)

    assert _windows(_storage(repo)) == []


def test_outside_a_git_repo_writes_none_and_returns_the_result(tmp_path):
    root = tmp_path / "plain"
    _write(root, "pathly/features/demo/IMPLEMENTATION_PLAN.md", "# Plan\n")
    calls: list = []
    spawn, expected = _editing_spawn(root, calls)

    result = spawn_window.observe(
        _state(root), FLOOR_FLOW, "builder", "demo-1-1", spawn
    )

    assert result is expected
    assert calls == [1]
    assert (root / "src" / "app.py").read_text(encoding="utf-8").startswith("def add")
    assert _windows(_storage(root)) == []


@pytest.mark.parametrize(
    "module, name", [(tree, "snapshot"), (eventlog, "append_event")]
)
def test_a_snapshot_or_event_failure_is_swallowed(repo, monkeypatch, module, name):
    def broken(*args, **kwargs):
        raise OSError("git exploded, or the database is locked")

    monkeypatch.setattr(module, name, broken)
    calls: list = []
    spawn, expected = _editing_spawn(repo, calls)

    result = spawn_window.observe(
        _state(repo), FLOOR_FLOW, "builder", "demo-1-1", spawn
    )

    assert result is expected
    assert calls == [1]
    assert _windows(_storage(repo)) == []


def test_without_a_storage_path_the_window_lands_in_the_topic_dir(repo):
    from pathly_orchestrator.fsm_ops import _resolve_storage_path

    calls: list = []
    spawn, _ = _editing_spawn(repo, calls)

    spawn_window.observe(
        _state(repo, storage=""), FLOOR_FLOW, "builder", "demo-1-1", spawn
    )

    resolved = _resolve_storage_path(None, str(repo), "demo")
    assert resolved == _storage(repo)
    (window,) = _windows(resolved)
    assert window["role"] == "builder"


# ── the two single-path spawn sites ──────────────────────────────────────────


def _team_build_with_a_floor_gate() -> dict:
    """The packaged team-build flow plus the floor gate ticket 06 adds at BUILDING->REVIEWING.

    Since ticket 08 the packaged flow ends BUILDING->REVIEWING with a ``scope_gate``, so it
    records windows on its own; the added floor gate keeps this test independent of that.
    """
    from pathly_orchestrator.fsm_ops import _load_flow

    flow = copy.deepcopy(_load_flow("team-build"))
    assert flow["role_map"]["BUILDING"] == "builder"
    assert spawn_window.wants_windows(flow) is True
    flow["gates"]["BUILDING->REVIEWING"].append(
        {"type": "floor_gate", "on_fail": "FLOOR_FAILURES.md"}
    )
    return flow


def test_fan_out_run_stage_on_team_build_records_builder_for_building(
    repo, monkeypatch
):
    import pathly_orchestrator.supervisor as _sup

    calls: list = []
    returned = {"ok": True, "cost_usd": 0.5, "session_id": "s-2"}

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        calls.append((state, instructions, adapter, model, run_id, broadcast_fn, kw))
        _write(repo, "src/app.py", "def add(a, b):\n    return a - b\n")
        return returned

    monkeypatch.setattr(_sup, "_run_stage_via_terminal", fake_spawn)
    state = _state(repo)
    args = ("build it", "claude", "claude-sonnet-4-6", "demo-1-300", None)
    flow = _team_build_with_a_floor_gate()

    result = fan_out.run_stage(
        state, flow, "BUILDING", *args, session="s-1", autonomy=False
    )

    assert result is returned
    assert calls == [(state, *args, {"session": "s-1", "autonomy": False})]
    (window,) = _windows(_storage(repo))
    assert window["role"] == "builder"
    assert window["state"] == "BUILDING"
    assert window["run_id"] == "demo-1-300"
    assert tree.changes(repo, window["before"], window["after"]) == [
        ("M", "src/app.py")
    ]


def test_the_feedback_spawn_records_its_target_as_the_role(repo, monkeypatch):
    """A planner routed IMPL_QUESTIONS inside REVIEWING is recorded as ``planner``.

    ``terminal_identity._spawn_role`` would read the flow's agent for REVIEWING and say
    ``reviewer``; the window must carry the feedback's own ``target_agent``.
    """
    import pathly_orchestrator.supervisor as _sup
    from pathly_orchestrator.supervisor.orchestrator_stage import (
        _resolve_stage_supervised,
    )
    from pathly_orchestrator.supervisor.state import RunnerState

    flow = {
        "role_map": {"REVIEWING": "reviewer"},
        "gates": {"REVIEWING->TESTING": [{"type": "reviewer_unchanged"}]},
    }
    loaded: list = []

    def fake_load(name, project_root):
        loaded.append((name, project_root))
        return flow

    monkeypatch.setattr(fan_out, "load_flow_config", fake_load)
    spawned: list = []

    def fake_spawn(state, instructions, adapter, model, run_id, broadcast_fn, **kw):
        spawned.append((instructions, run_id, kw))
        _write(
            repo,
            "pathly/features/demo/IMPLEMENTATION_PLAN.md",
            "# Plan\n\nAnswered.\n",
        )
        return {"ok": True}

    monkeypatch.setattr(_sup, "_run_stage_via_terminal", fake_spawn)
    state = RunnerState(
        topic="demo",
        flow="team-build",
        project_root=str(repo),
        model="claude-sonnet-4-6",
        timeout=60,
        current_state="REVIEWING",
        current_adapter="claude",
        storage_path=str(_storage(repo)),
    )
    # complete_stage answers from a script: blocked on the planner's file, then advance.
    answers = [
        {
            "blocked": True,
            "target_agent": "planner",
            "file": "IMPL_QUESTIONS.md",
            "instructions": "Answer the builder's question in the plan.",
        },
        {"next_state": "TESTING"},
    ]
    payloads: list = []
    fhc = SimpleNamespace(complete_stage=lambda p: payloads.append(p) or answers.pop(0))

    result = _resolve_stage_supervised(
        state, "team-build", "demo", str(repo), "claude-sonnet-4-6", None, fhc
    )

    assert result == {"next_state": "TESTING"}
    assert loaded == [("team-build", str(repo))]
    assert len(spawned) == 1
    instructions, run_id, kw = spawned[0]
    assert instructions == "Answer the builder's question in the plan."
    assert kw["session"] is None
    (window,) = _windows(_storage(repo))
    assert window["role"] == "planner"
    assert window["state"] == "REVIEWING"
    assert window["run_id"] == run_id
    assert run_id.startswith("demo-fb1-")
    assert tree.changes(repo, window["before"], window["after"]) == [
        ("M", "pathly/features/demo/IMPLEMENTATION_PLAN.md")
    ]
    assert payloads[1]["resolved_files"] == ["IMPL_QUESTIONS.md"]
