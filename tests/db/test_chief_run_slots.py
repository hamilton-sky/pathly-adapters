"""chief-agent 15: the run counter of a chief session (``chief_sessions.runs_started``).

``take_run_slot`` is one conditional UPDATE, so two writers cannot both take the last slot;
``give_back_run_slot`` never takes the count below zero.
"""

from __future__ import annotations

import threading

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries import chief


def _open(conn, run_id="chief-1"):
    chief.create_session(
        conn,
        run_id=run_id,
        project_root="/work/proj",
        preset="operator",
        tier="operator",
        engine="claude",
        tab_id="tab-" + run_id,
        cli_session_id=None,
        hook_secret_hash=None,
        settings_dir=None,
    )


def _count(conn, run_id="chief-1") -> int:
    row = conn.execute(
        "SELECT runs_started FROM chief_sessions WHERE run_id = ?", (run_id,)
    )
    return row.fetchone()[0]


def test_a_new_session_has_taken_no_slot():
    conn = get_db()
    _open(conn)

    assert _count(conn) == 0
    assert chief.get_session(conn, "chief-1")["runs_started"] == 0


def test_slots_are_taken_up_to_the_limit_and_no_further():
    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    conn = get_db()
    _open(conn)

    taken = [take_run_slot(conn, "chief-1", 3) for _ in range(5)]

    assert taken == [True, True, True, False, False]
    assert _count(conn) == 3


def test_a_limit_of_zero_or_below_takes_nothing():
    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    conn = get_db()
    _open(conn)

    assert [take_run_slot(conn, "chief-1", n) for n in (0, -1, -100)] == [False] * 3
    assert _count(conn) == 0


def test_a_session_that_does_not_exist_has_no_slot_to_take():
    from pathly_orchestrator.db.queries.chief_run_slots import (
        give_back_run_slot,
        take_run_slot,
    )

    conn = get_db()

    assert take_run_slot(conn, "nobody", 5) is False
    assert give_back_run_slot(conn, "nobody") is False


def test_a_raised_limit_makes_room_for_the_same_session():
    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    conn = get_db()
    _open(conn)
    assert take_run_slot(conn, "chief-1", 1) and not take_run_slot(conn, "chief-1", 1)

    assert take_run_slot(conn, "chief-1", 2) is True
    assert _count(conn) == 2


def test_a_lowered_limit_takes_nothing_from_a_session_already_over_it():
    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    conn = get_db()
    _open(conn)
    for _ in range(3):
        take_run_slot(conn, "chief-1", 10)

    assert take_run_slot(conn, "chief-1", 2) is False
    assert _count(conn) == 3


def test_giving_a_slot_back_stops_at_zero():
    from pathly_orchestrator.db.queries.chief_run_slots import (
        give_back_run_slot,
        take_run_slot,
    )

    conn = get_db()
    _open(conn)
    take_run_slot(conn, "chief-1", 5)
    take_run_slot(conn, "chief-1", 5)

    results = [give_back_run_slot(conn, "chief-1") for _ in range(4)]

    assert results == [True, True, False, False]
    assert _count(conn) == 0


def test_one_session_does_not_touch_another():
    from pathly_orchestrator.db.queries.chief_run_slots import (
        give_back_run_slot,
        take_run_slot,
    )

    conn = get_db()
    _open(conn, "a")
    _open(conn, "b")

    take_run_slot(conn, "a", 5)
    take_run_slot(conn, "a", 5)
    take_run_slot(conn, "b", 5)
    give_back_run_slot(conn, "a")

    assert (_count(conn, "a"), _count(conn, "b")) == (1, 1)


def test_a_closed_session_keeps_the_count_it_had():
    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    conn = get_db()
    _open(conn)
    take_run_slot(conn, "chief-1", 5)

    chief.close_session(conn, "chief-1", "tab closed")

    assert _count(conn) == 1


def test_threads_cannot_take_more_slots_than_the_limit():
    from pathly_orchestrator.db.queries.chief_run_slots import take_run_slot

    _open(get_db())
    gate = threading.Barrier(16)
    won: list[bool] = []
    errors: list[BaseException] = []

    def take() -> None:
        try:
            conn = get_db()
            gate.wait(timeout=10)
            won.append(take_run_slot(conn, "chief-1", 5))
        except BaseException as exc:  # reported on the test's thread below
            errors.append(exc)

    threads = [threading.Thread(target=take) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert errors == []
    assert sorted(won) == [False] * 11 + [True] * 5
    assert _count(get_db()) == 5
