"""`lane` + `files` have a write path, and the partition is checkable (fan-out C.5).

Both columns existed in the schema with NO writer: `post_message` never accepted `lane`, and
`/comms/post` — the only way an agent creates a task — never forwarded `files`. So every task
reached the scheduler with both NULL, and `scheduler.py`'s `lane or task_id` fallback put each
task in its own lane. That makes "at most one worker per lane" vacuously true, which is fine
under SerialIsolation (Phase C) and worthless the moment isolation goes parallel: N tasks, N
lanes, N concurrent agents on one working tree with nothing checking their footprints.

These tests pin the two halves of the fix — the write path, and `audit_lane_partition`, which
checks the disjoint-files-per-lane assumption `LaneIsolation`'s docstring makes rather than
trusting it.
"""

from __future__ import annotations

import json

import pytest

from pathly_orchestrator.supervisor.lane_partition import audit_lane_partition


def _post(client, **over):
    body = {
        "board": "feature",
        "feature": "lanes",
        "from": "planner",
        "type": "task",
        "text": "a task",
    }
    body.update(over)
    return client.post("/comms/post", json=body)


@pytest.fixture
def client():
    from pathly_orchestrator.http_server import app

    with app.test_client() as c:
        yield c


def _task(conn, scope, text, lane=None, files=None, depends_on=None):
    from pathly_orchestrator.db.queries.comms import post_message

    mid = post_message(
        conn,
        board="feature",
        scope=scope,
        from_agent="planner",
        type="task",
        text=text,
        lane=lane,
        files=files,
        depends_on=depends_on,
    )
    conn.execute("UPDATE comms_messages SET task_status='pending' WHERE id=?", (mid,))
    conn.commit()
    return mid


# ── The write path ───────────────────────────────────────────────────────────


def test_post_message_persists_lane_and_files():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    mid = _task(conn, "w1", "t", lane="backend", files=["src/api.py"])
    row = conn.execute(
        "SELECT lane, files FROM comms_messages WHERE id=?", (mid,)
    ).fetchone()
    assert row["lane"] == "backend"
    assert json.loads(row["files"]) == ["src/api.py"]


def test_comms_post_route_forwards_lane_and_files(client):
    """The route is the ONLY path an agent has — a column it drops may as well not exist."""
    from pathly_orchestrator.db.connection import get_db

    resp = _post(
        client,
        text="implement the API",
        lane="backend",
        files=["src/api/routes.py", "src/api/models.py"],
    )
    assert resp.status_code == 200
    row = (
        get_db()
        .execute(
            "SELECT lane, files FROM comms_messages WHERE text='implement the API'"
        )
        .fetchone()
    )
    assert row["lane"] == "backend"
    assert json.loads(row["files"]) == ["src/api/routes.py", "src/api/models.py"]


def test_omitting_both_is_still_accepted(client):
    """Back-compat: every existing caller posts neither field."""
    from pathly_orchestrator.db.connection import get_db

    assert _post(client, text="no footprint").status_code == 200
    row = (
        get_db()
        .execute("SELECT lane, files FROM comms_messages WHERE text='no footprint'")
        .fetchone()
    )
    assert row["lane"] is None and row["files"] is None


@pytest.mark.parametrize(
    "bad,field",
    [
        ({"lane": ""}, "lane"),
        ({"lane": "   "}, "lane"),
        ({"lane": 7}, "lane"),
        ({"files": "src/a.py"}, "files"),
        ({"files": [1, 2]}, "files"),
        ({"files": {"a": 1}}, "files"),
    ],
)
def test_route_rejects_malformed_lane_or_files(client, bad, field):
    resp = _post(client, text="bad", **bad)
    assert resp.status_code == 400
    assert field in (resp.get_json() or {}).get("error", "")


# ── The audit ────────────────────────────────────────────────────────────────


def test_disjoint_lanes_are_safe():
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    _task(conn, "ok", "backend work", lane="backend", files=["src/api.py"])
    _task(conn, "ok", "frontend work", lane="frontend", files=["web/app.tsx"])

    report = audit_lane_partition(conn, "feature", "ok")
    assert report["safe"] is True
    assert report["tasks"] == 2
    assert report["conflicts"] == [] and report["undeclared"] == []


def test_overlapping_files_in_different_lanes_is_a_conflict():
    """The exact hazard: two lanes, same file — the scheduler would run them at once."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    a = _task(conn, "clash", "A", lane="backend", files=["src/api.py"])
    b = _task(conn, "clash", "B", lane="frontend", files=["src/api.py", "web/x.tsx"])

    report = audit_lane_partition(conn, "feature", "clash")
    assert report["safe"] is False
    assert "cross-lane file overlap" in report["reason"]
    (conflict,) = report["conflicts"]
    assert {conflict["a"], conflict["b"]} == {a, b}
    assert conflict["files"] == ["src/api.py"]


def test_overlapping_files_in_the_SAME_lane_is_safe():
    """Same lane is exactly how a planner declares 'these must not run together'."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    _task(conn, "sharedlane", "A", lane="backend", files=["src/api.py"])
    _task(conn, "sharedlane", "B", lane="backend", files=["src/api.py"])

    report = audit_lane_partition(conn, "feature", "sharedlane")
    assert report["safe"] is True, "the scheduler already serialises one lane"


def test_directory_containment_counts_as_overlap():
    """`file_claims` treats `src/api` as covering `src/api/routes.py` — so must the audit."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    _task(conn, "dirs", "A", lane="one", files=["src/api"])
    _task(conn, "dirs", "B", lane="two", files=["src/api/routes.py"])

    assert audit_lane_partition(conn, "feature", "dirs")["safe"] is False


def test_an_undeclared_footprint_is_unsafe_not_assumed_fine():
    """No declared files = unknown footprint = the WILDCARD that overlaps everything."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    _task(conn, "undecl", "A", lane="backend", files=["src/api.py"])
    bare = _task(conn, "undecl", "B", lane="frontend")  # no files

    report = audit_lane_partition(conn, "feature", "undecl")
    assert report["safe"] is False
    assert report["undeclared"] == [bare]
    assert "declare no files" in report["reason"]


def test_todays_production_dag_audits_as_unsafe():
    """The pre-C.5 status quo, stated as a test: nothing declared anything.

    This is why Phase D could not be a one-line isolation swap — on this data
    `LaneIsolation` would have run every task at once with no footprint to check.
    """
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    for n in range(4):
        _task(conn, "legacy", f"task-{n}")  # no lane, no files — as agents post today

    report = audit_lane_partition(conn, "feature", "legacy")
    assert report["safe"] is False
    assert len(report["undeclared"]) == 4


def test_an_empty_frontier_is_safe():
    """A drained board must not read as unsafe — that would block on nothing."""
    from pathly_orchestrator.db.connection import get_db

    assert audit_lane_partition(get_db(), "feature", "nothing-here")["safe"] is True


def test_blocked_tasks_are_not_audited():
    """Only the READY frontier can run concurrently; `depends_on` already serialises the rest."""
    from pathly_orchestrator.db.connection import get_db

    conn = get_db()
    first = _task(conn, "dep", "first", lane="one", files=["src/shared.py"])
    _task(
        conn, "dep", "second", lane="two", files=["src/shared.py"], depends_on=[first]
    )

    report = audit_lane_partition(conn, "feature", "dep")
    assert report["tasks"] == 1, "the dependent task is not on the frontier"
    assert report["safe"] is True, "a task that cannot run yet cannot collide"


def test_audit_never_raises_on_a_bad_connection():
    """Read-only and defensive — an audit must never be able to break a run."""

    class _Broken:
        def execute(self, *a, **k):
            raise RuntimeError("db is gone")

    report = audit_lane_partition(_Broken(), "feature", "x")
    assert report["safe"] is False and report["reason"]
