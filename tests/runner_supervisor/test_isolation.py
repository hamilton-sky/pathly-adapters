"""Tests for supervisor/isolation.py — LaneIsolation workspace seam."""

from __future__ import annotations

import pytest

from pathly_orchestrator.supervisor.isolation import (
    LaneIsolation,
    TaskWorkspace,
    WorktreeIsolation,
)


class _FakeState:
    """Minimal stand-in for RunnerState with the fields isolation.py reads."""

    def __init__(
        self,
        project_root: str = "/repo",
        db_path: str = "/db/pathly.db",
        fsm_port: int = 8765,
    ):
        self.project_root = project_root
        self.db_path = db_path
        self.fsm_port = fsm_port


class TestTaskWorkspace:
    def test_frozen(self):
        ws = TaskWorkspace(cwd="/repo")
        with pytest.raises((AttributeError, TypeError)):
            ws.cwd = "/other"  # type: ignore[misc]

    def test_defaults(self):
        ws = TaskWorkspace(cwd="/repo")
        assert ws.env == {}
        assert ws.lease_id == ""


class TestLaneIsolation:
    def test_acquire_builds_correct_workspace(self):
        iso = LaneIsolation()
        state = _FakeState(
            project_root="/my/repo",
            db_path="/home/user/.pathly/pathly.db",
            fsm_port=8765,
        )
        task = {"id": "task-abc-123", "lane": "backend"}

        ws = iso.acquire(task, state)

        assert isinstance(ws, TaskWorkspace)
        assert ws.cwd == "/my/repo"
        assert ws.env["PATHLY_DB_PATH"] == "/home/user/.pathly/pathly.db"
        assert ws.env["PATHLY_FSM_HTTP_PORT"] == "8765"
        assert ws.lease_id == "task-abc-123"

    def test_acquire_port_is_stringified(self):
        iso = LaneIsolation()
        state = _FakeState(fsm_port=9999)
        ws = iso.acquire({"id": "t1"}, state)
        assert ws.env["PATHLY_FSM_HTTP_PORT"] == "9999"

    def test_release_is_noop(self):
        iso = LaneIsolation()
        ws = TaskWorkspace(cwd="/repo", lease_id="t1")
        # Must not raise for either outcome.
        iso.release(ws, success=True)
        iso.release(ws, success=False)

    def test_max_concurrency_returns_lane_count(self):
        iso = LaneIsolation()
        assert iso.max_concurrency({"a", "b"}) == 2
        assert iso.max_concurrency({"backend", "frontend", "tests"}) == 3

    def test_max_concurrency_minimum_one(self):
        iso = LaneIsolation()
        assert iso.max_concurrency(set()) == 1

    def test_max_concurrency_single_lane(self):
        iso = LaneIsolation()
        assert iso.max_concurrency({"backend"}) == 1


class TestWorktreeIsolation:
    def test_acquire_raises_not_implemented(self):
        iso = WorktreeIsolation()
        with pytest.raises(NotImplementedError, match="P3"):
            iso.acquire({"id": "t1"}, _FakeState())

    def test_release_raises_not_implemented(self):
        iso = WorktreeIsolation()
        ws = TaskWorkspace(cwd="/wt/t1")
        with pytest.raises(NotImplementedError, match="P3"):
            iso.release(ws, success=True)

    def test_max_concurrency_raises_not_implemented(self):
        iso = WorktreeIsolation()
        with pytest.raises(NotImplementedError, match="P3"):
            iso.max_concurrency({"a"})
