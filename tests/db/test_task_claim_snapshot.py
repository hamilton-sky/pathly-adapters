"""build-proof 03: a task's text is frozen at its first claim, and its floor allow list is stored.

``claim_task`` copies ``text`` into ``claimed_text`` once (``COALESCE``), so a builder that edits
its task between attempts cannot change the checks it is proven against. Only
``set_floor_allow(..., refreeze=True)`` (the human route) copies the live text again.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.migrations import _run_migrations
from pathly_orchestrator.db.queries.comms_messages import (
    post_message,
    soft_delete_message,
    update_message_text,
)
from pathly_orchestrator.db.queries.comms_tasks import claim_task, complete_task
from pathly_orchestrator.db.queries.task_proof import (
    get_task,
    set_floor_allow,
    tasks_claimed_since,
    tasks_completed_since,
)
from pathly_orchestrator.supervisor.task_retry import retry_task

# Isolation is handled by the _isolate_db autouse fixture in conftest.py.
NEW_COLUMNS = {"claimed_text", "floor_allow"}
FIRST = "Add the widget.\n\n```check\n$ python -m pytest tests/test_widget.py -q\n```\n"
SECOND = 'Add the widget.\n\n```check\n$ python -c "print(1)"\n```\n'
LONG_AGO = "2020-01-01T00:00:00+00:00"


def _columns(conn) -> set[str]:
    return {r["name"] for r in conn.execute("PRAGMA table_info(comms_messages)")}


def _task(conn, text: str = FIRST, *, scope: str = "feat", goal_id=None) -> str:
    return post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        goal_id=goal_id,
    )


def _zulu(delta_seconds: float = 0.0) -> str:
    """A UTC stamp in the ``...Z`` form event ``ts`` values use."""
    when = datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)
    return when.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


_SET_STAMP = {
    "claimed_at": "UPDATE comms_messages SET claimed_at=? WHERE id=?",
    "completed_at": "UPDATE comms_messages SET completed_at=? WHERE id=?",
}
_DROP_COLUMN = {
    "claimed_text": "ALTER TABLE comms_messages DROP COLUMN claimed_text",
    "floor_allow": "ALTER TABLE comms_messages DROP COLUMN floor_allow",
}


def _set(conn, task_id: str, column: str, value: str) -> None:
    conn.execute(_SET_STAMP[column], (value, task_id))
    conn.commit()


def _ids(rows: list[dict]) -> set[str]:
    return {r["id"] for r in rows}


def test_a_fresh_db_has_both_columns() -> None:
    assert NEW_COLUMNS <= _columns(get_db())


def test_an_old_db_without_the_columns_gets_them_and_old_rows_read_null() -> None:
    conn = get_db()
    # Make this DB look like one written before the feature: no columns, one claimed task.
    for column in NEW_COLUMNS & _columns(conn):
        conn.execute(_DROP_COLUMN[column])
    conn.commit()
    assert not NEW_COLUMNS & _columns(conn)
    tid = _task(conn)
    conn.execute(
        "UPDATE comms_messages SET task_status='in_progress', claimed_at=? WHERE id=?",
        (LONG_AGO, tid),
    )
    conn.commit()

    _run_migrations(conn)
    _run_migrations(conn)  # a second pass is a clean no-op

    assert NEW_COLUMNS <= _columns(conn)
    row = get_task(conn, tid)
    assert row is not None
    assert row["claimed_text"] is None
    assert row["floor_allow"] is None


def test_a_task_never_claimed_has_no_frozen_text() -> None:
    conn = get_db()
    tid = _task(conn)
    row = get_task(conn, tid)
    assert row is not None
    assert row["claimed_text"] is None


def test_the_first_claim_freezes_the_text() -> None:
    conn = get_db()
    tid = _task(conn)
    assert claim_task(conn, tid, run_id="sched-x#1")
    row = get_task(conn, tid)
    assert row is not None
    assert row["claimed_text"] == FIRST
    assert row["task_status"] == "in_progress"
    assert row["attempts"] == 1


def test_a_retry_and_a_second_claim_keep_the_first_text() -> None:
    conn = get_db()
    tid = _task(conn)
    assert claim_task(conn, tid, run_id="sched-x#1")
    update_message_text(conn, tid, SECOND)  # the builder edits its own task
    retry_task(conn, tid, "check failed")
    assert claim_task(conn, tid, run_id="sched-x#2")

    row = get_task(conn, tid)
    assert row is not None
    assert row["text"] == SECOND
    assert row["claimed_text"] == FIRST
    assert row["attempts"] == 2


def test_a_team_flow_claim_freezes_the_text_too() -> None:
    conn = get_db()
    tid = _task(conn)
    assert claim_task(conn, tid, run_id="build")
    row = get_task(conn, tid)
    assert row is not None
    assert row["claimed_text"] == FIRST


def test_set_floor_allow_stores_a_json_list_and_keeps_the_frozen_text() -> None:
    conn = get_db()
    tid = _task(conn)
    assert claim_task(conn, tid, run_id="sched-x#1")
    update_message_text(conn, tid, SECOND)

    assert set_floor_allow(conn, tid, ["skip", "config", "skip"]) is True

    row = get_task(conn, tid)
    assert row is not None
    assert json.loads(row["floor_allow"]) == ["config", "skip"]
    assert row["claimed_text"] == FIRST


def test_set_floor_allow_with_refreeze_copies_the_live_text() -> None:
    conn = get_db()
    tid = _task(conn)
    assert claim_task(conn, tid, run_id="sched-x#1")
    update_message_text(conn, tid, SECOND)  # a human corrects a broken check

    assert set_floor_allow(conn, tid, ["skip"], refreeze=True) is True

    row = get_task(conn, tid)
    assert row is not None
    assert row["claimed_text"] == SECOND
    assert json.loads(row["floor_allow"]) == ["skip"]


def test_set_floor_allow_with_an_empty_list_clears_the_allowance() -> None:
    conn = get_db()
    tid = _task(conn)
    set_floor_allow(conn, tid, ["skip"])
    assert set_floor_allow(conn, tid, []) is True
    row = get_task(conn, tid)
    assert row is not None
    assert json.loads(row["floor_allow"]) == []


def test_set_floor_allow_changes_nothing_for_a_missing_or_non_task_row() -> None:
    conn = get_db()
    note = post_message(
        conn, board="feature", scope="feat", from_agent="human", type="decision"
    )
    assert set_floor_allow(conn, "no-such-id", ["skip"]) is False
    assert set_floor_allow(conn, note, ["skip"]) is False
    row = get_task(conn, note)
    assert row is not None
    assert row["floor_allow"] is None


def test_get_task_reads_any_live_row_and_none_for_a_missing_or_deleted_one() -> None:
    conn = get_db()
    tid = _task(conn)
    note = post_message(
        conn, board="feature", scope="feat", from_agent="human", type="decision"
    )
    gone = _task(conn)
    soft_delete_message(conn, gone, force=True)

    task = get_task(conn, tid)
    assert task is not None and task["type"] == "task" and task["text"] == FIRST
    decision = get_task(conn, note)
    assert decision is not None and decision["type"] == "decision"
    assert get_task(conn, "no-such-id") is None
    assert get_task(conn, gone) is None


def test_tasks_claimed_since_respects_goal_id() -> None:
    conn = get_db()
    since = _zulu(-1)
    in_g1 = _task(conn, goal_id="g1")
    in_g2 = _task(conn, goal_id="g2")
    no_goal = _task(conn)
    other_scope = _task(conn, scope="other")
    unclaimed_g1 = _task(conn, goal_id="g1")
    old_g1 = _task(conn, goal_id="g1")
    for tid in (in_g1, in_g2, no_goal, other_scope, old_g1):
        assert claim_task(conn, tid, run_id="sched-" + tid + "#1")
    _set(conn, old_g1, "claimed_at", LONG_AGO)

    by_goal = tasks_claimed_since(conn, "feature", "feat", "g1", since)
    by_scope = tasks_claimed_since(conn, "feature", "feat", None, since)

    assert _ids(by_goal) == {in_g1}
    assert _ids(by_scope) == {in_g1, in_g2, no_goal}
    assert unclaimed_g1 not in _ids(by_scope) | _ids(by_goal)
    assert by_goal[0]["claimed_text"] == FIRST


def test_tasks_claimed_since_compares_times_not_strings() -> None:
    conn = get_db()
    tid = _task(conn)
    assert claim_task(conn, tid, run_id="sched-x#1")
    _set(conn, tid, "claimed_at", "2026-05-01T10:00:00.250000+00:00")

    # The same instant written as `Z`, and as `+00:00` without fractions.
    assert _ids(
        tasks_claimed_since(conn, "feature", "feat", None, "2026-05-01T10:00:00.25Z")
    ) == {tid}
    assert _ids(
        tasks_claimed_since(conn, "feature", "feat", None, "2026-05-01T10:00:00+00:00")
    ) == {tid}
    assert (
        tasks_claimed_since(conn, "feature", "feat", None, "2026-05-01T10:00:01Z") == []
    )
    assert _ids(
        tasks_claimed_since(
            conn,
            "feature",
            "feat",
            None,
            datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc),
        )
    ) == {tid}


def test_tasks_completed_since_respects_goal_id_status_and_window() -> None:
    conn = get_db()
    since = _zulu(-1)
    done_g1 = _task(conn, goal_id="g1")
    done_g2 = _task(conn, goal_id="g2")
    old_done_g1 = _task(conn, goal_id="g1")
    claimed_g1 = _task(conn, goal_id="g1")
    other_scope = _task(conn, scope="other", goal_id="g9")
    for tid in (done_g1, done_g2, old_done_g1, claimed_g1, other_scope):
        assert claim_task(conn, tid, run_id="sched-" + tid + "#1")
    for tid in (done_g1, done_g2, old_done_g1, other_scope):
        complete_task(conn, tid)
    _set(conn, old_done_g1, "completed_at", LONG_AGO)

    assert _ids(tasks_completed_since(conn, "feature", "feat", "g1", since)) == {
        done_g1
    }
    assert _ids(tasks_completed_since(conn, "feature", "feat", None, since)) == {
        done_g1,
        done_g2,
    }
