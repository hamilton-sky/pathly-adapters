"""unified-control-plane: post_message stamps run_id so board posts correlate to their run.

Closes the dead comms_messages.run_id column (the read-model already JOINs on it, but nothing
wrote it) — the control plane's RunDetail Board tab can now show a run's EXACT posts instead of
an approximate time-window guess. Isolation via the top-level _isolate_db autouse fixture.
"""

from __future__ import annotations

from pathly_orchestrator.db import get_db
from pathly_orchestrator.db.queries.comms_messages import post_message


def test_post_message_stamps_run_id() -> None:
    conn = get_db()
    mid = post_message(
        conn, board="feat-x", scope="feat-x", from_agent="system",
        type="status", text="run started", run_id="run-abc",
    )
    row = conn.execute("SELECT run_id FROM comms_messages WHERE id=?", (mid,)).fetchone()
    assert row["run_id"] == "run-abc"


def test_post_message_run_id_defaults_null() -> None:
    conn = get_db()
    mid = post_message(
        conn, board="feat-x", scope="feat-x", from_agent="system", type="status", text="no run",
    )
    row = conn.execute("SELECT run_id FROM comms_messages WHERE id=?", (mid,)).fetchone()
    assert row["run_id"] is None


def test_run_id_correlates_posts_to_a_run() -> None:
    """Two posts on the same board, different runs — each is retrievable by its own run_id."""
    conn = get_db()
    a = post_message(conn, board="b", scope="b", from_agent="system", type="status",
                     text="A", run_id="run-1")
    b = post_message(conn, board="b", scope="b", from_agent="system", type="status",
                     text="B", run_id="run-2")
    got = {r["id"] for r in conn.execute(
        "SELECT id FROM comms_messages WHERE run_id=?", ("run-1",)).fetchall()}
    assert a in got and b not in got
