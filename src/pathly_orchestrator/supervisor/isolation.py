"""Isolation seam for the DAG task scheduler.

Provides a pluggable workspace abstraction so the scheduler can spawn tasks
without knowing whether it is using a shared worktree (P2) or per-task git
worktrees (P3).

See: pathly/plans/comms-board/DAG-SCHEDULER-ARCHITECTURE.md §2
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class TaskWorkspace:
    """Everything a worker needs to run a task in isolation."""

    cwd: str
    env: dict[str, str] = field(default_factory=dict)
    #   env carries PATHLY_DB_PATH + PATHLY_FSM_HTTP_PORT (see §5).
    #   For LaneIsolation these are the shared run's values (single DB/port).
    lease_id: str = ""  # opaque handle returned to release()


class Isolation(Protocol):
    """Give me an isolated workspace + DB + port for this task, then take it back."""

    def acquire(self, task: dict, state) -> TaskWorkspace:
        """Reserve resources for `task`. `task` is a comms_messages row dict
        (id, lane, text, depends_on, ...). May block briefly to allocate a port
        or create a worktree. MUST be idempotent w.r.t. lease_id on retry."""
        ...

    def release(self, ws: TaskWorkspace, *, success: bool) -> None:
        """Release the workspace. success=False may keep the workspace around
        for inspection (worktree impl) or be a no-op (lane impl)."""
        ...

    def max_concurrency(self, ready_lanes: set[str]) -> int:
        """Upper bound on simultaneous workers given the current ready lanes.
        LaneIsolation -> len(ready_lanes). WorktreeIsolation -> a fixed pool size."""
        ...


class LaneIsolation:
    """Same worktree, no merge. Concurrency safety comes from the scheduler's
    <=1-worker-per-lane rule (disjoint file sets per lane), NOT from per-task
    workspaces. Every task gets the SHARED run cwd/db/port."""

    def acquire(self, task: dict, state) -> TaskWorkspace:
        return TaskWorkspace(
            cwd=state.project_root,
            env={
                "PATHLY_DB_PATH": state.db_path,
                "PATHLY_FSM_HTTP_PORT": str(state.fsm_port),
            },
            lease_id=task["id"],
        )

    def release(self, ws: TaskWorkspace, *, success: bool) -> None:
        return  # nothing to free; lane is freed by the scheduler, not here

    def max_concurrency(self, ready_lanes: set[str]) -> int:
        return max(1, len(ready_lanes))  # one worker per active lane


class SerialIsolation:
    """Lane isolation pinned to ONE worker at a time — the Phase-1 "ship serial"
    executor. Delegates workspace acquire/release to an inner LaneIsolation but
    forces max_concurrency to 1 regardless of how many lanes are ready, so the
    frontier drains one task at a time. Flipping to parallel (P3) is just swapping
    this back to LaneIsolation (across-goal) or WorktreeIsolation (within-goal)."""

    def __init__(self) -> None:
        self._inner = LaneIsolation()

    def acquire(self, task: dict, state) -> TaskWorkspace:
        return self._inner.acquire(task, state)

    def release(self, ws: TaskWorkspace, *, success: bool) -> None:
        self._inner.release(ws, success=success)

    def max_concurrency(self, ready_lanes: set[str]) -> int:
        return 1


class WorktreeIsolation:
    """Per-task git worktree + private DB + private port.

    Enables SAME-lane parallelism with a fan-in merge step the scheduler runs
    after release(). This class is a documented stub for P3 — do not implement
    worktrees in P2.

    See: pathly/plans/comms-board/DAG-SCHEDULER-ARCHITECTURE.md §2.2
    """

    def acquire(self, task: dict, state) -> TaskWorkspace:
        raise NotImplementedError("P3")

    def release(self, ws: TaskWorkspace, *, success: bool) -> None:
        raise NotImplementedError("P3")

    def max_concurrency(self, ready_lanes: set[str]) -> int:
        raise NotImplementedError("P3")
