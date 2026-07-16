"""Tests for the per-board run-lock (BOARD-RUNTIME-SPEC A2/D1)."""

from __future__ import annotations

import threading

import pytest

from pathly_orchestrator.supervisor import board_lock


@pytest.fixture(autouse=True)
def _clear():
    board_lock._held.clear()
    yield
    board_lock._held.clear()


def test_acquire_then_second_is_rejected():
    assert board_lock.acquire("feature", "f1", "run-a") is True
    assert board_lock.is_locked("feature", "f1") is True
    # A different runner cannot take a held board.
    assert board_lock.acquire("feature", "f1", "run-b") is False


def test_reacquire_same_run_is_idempotent():
    assert board_lock.acquire("global", "global", "run-a") is True
    assert board_lock.acquire("global", "global", "run-a") is True  # retry, same owner


def test_release_frees_the_board():
    board_lock.acquire("project", "C:/p", "run-a")
    assert board_lock.release("project", "C:/p", "run-a") is True
    assert board_lock.is_locked("project", "C:/p") is False
    # now another runner can take it
    assert board_lock.acquire("project", "C:/p", "run-b") is True


def test_release_with_wrong_run_id_is_refused():
    board_lock.acquire("feature", "f1", "run-a")
    assert board_lock.release("feature", "f1", "run-b") is False  # not the holder
    assert board_lock.is_locked("feature", "f1") is True


def test_distinct_boards_are_independent():
    assert board_lock.acquire("feature", "f1", "r1") is True
    assert board_lock.acquire("feature", "f2", "r2") is True  # different scope
    assert board_lock.acquire("global", "global", "r3") is True  # different board
    assert board_lock.holder("feature", "f1") == "r1"
    assert board_lock.holder("feature", "f2") == "r2"


def test_concurrent_acquire_exactly_one_winner():
    board_lock._held.clear()
    results: list[bool] = []
    rlock = threading.Lock()

    def worker(rid: str):
        won = board_lock.acquire("feature", "race", rid)
        with rlock:
            results.append(won)

    threads = [threading.Thread(target=worker, args=(f"r{i}",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(1 for w in results if w) == 1  # exactly one acquirer wins
