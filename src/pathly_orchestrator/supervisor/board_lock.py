"""Per-board run-lock — enforces "one active runner per board" (BOARD-RUNTIME-SPEC D1).

A board is identified by (board, scope): e.g. ("feature", "my-feature"),
("project", "C:/proj"), ("global", "global"). At most one runner — a single agent
OR a flow — may own a given board at a time. Acquisition is atomic under a lock;
a second acquire on a held board returns False so the HTTP layer can answer 409.

This is intentionally separate from the topic-keyed run registry: flow runs already
lock by topic in api.start_run, while board runs (single-agent, evaluator) lock here
by (board, scope). For feature boards the two keys coincide conceptually; the board
lock is the authoritative gate for board-initiated runs.
"""

from __future__ import annotations

import threading

# (board, scope) -> run_id currently holding the board.
_held: dict[tuple[str, str], str] = {}
_lock = threading.Lock()


def board_key(board: str, scope: str) -> tuple[str, str]:
    """Normalize a board identity into a lock key."""
    return (board or "", scope or "")


def acquire(board: str, scope: str, run_id: str) -> bool:
    """Atomically take the board's run-lock for run_id.

    Returns True if this caller now owns the board, False if it was already held.
    Re-acquiring with the SAME run_id returns True (idempotent for retries).
    """
    key = board_key(board, scope)
    with _lock:
        holder = _held.get(key)
        if holder is not None and holder != run_id:
            return False
        _held[key] = run_id
        return True


def release(board: str, scope: str, run_id: str | None = None) -> bool:
    """Release the board's run-lock.

    If run_id is given, only release when it matches the current holder (so a
    stale releaser cannot free a board taken over by someone else). Returns True
    if a lock was released.
    """
    key = board_key(board, scope)
    with _lock:
        holder = _held.get(key)
        if holder is None:
            return False
        if run_id is not None and holder != run_id:
            return False
        del _held[key]
        return True


def is_locked(board: str, scope: str) -> bool:
    """Return True if the board currently has an active runner."""
    with _lock:
        return board_key(board, scope) in _held


def holder(board: str, scope: str) -> str | None:
    """Return the run_id holding the board, or None."""
    with _lock:
        return _held.get(board_key(board, scope))
