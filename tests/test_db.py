"""Unit tests for pathly_orchestrator.db — all three tables."""
from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from pathly_orchestrator.db import (
    _conn_cache,
    _cache_lock,
    append_event,
    get_db,
    mark_stale_runners,
    read_events,
    read_last_agent_done,
    read_runner_state,
    read_state,
    write_runner_state,
    write_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _purge_cache(feature_dir: Path) -> None:
    """Remove the cached connection for a tmp_path DB so tests are isolated."""
    db_path = str(feature_dir.resolve() / "pathly.db")
    with _cache_lock:
        _conn_cache.pop(db_path, None)


# ---------------------------------------------------------------------------
# Schema / connection tests
# ---------------------------------------------------------------------------

def test_get_db_creates_tables(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    assert "fsm_events" in tables
    assert "fsm_state" in tables
    assert "runner_state" in tables
    _purge_cache(tmp_path)


def test_get_db_cached(tmp_path: Path) -> None:
    conn1 = get_db(tmp_path)
    conn2 = get_db(tmp_path)
    assert conn1 is conn2
    _purge_cache(tmp_path)


# ---------------------------------------------------------------------------
# fsm_events tests
# ---------------------------------------------------------------------------

def test_append_and_read_events(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    events = [
        {"type": "STATE_TRANSITION", "ts": "2026-01-01T00:00:01Z", "to": "PLAN"},
        {"type": "PHASE_START", "ts": "2026-01-01T00:00:02Z", "phase": "build"},
        {"type": "AGENT_DONE", "ts": "2026-01-01T00:00:03Z", "summary": "done"},
    ]
    for e in events:
        append_event(conn, "feat-a", e)

    result = read_events(conn, "feat-a")
    assert len(result) == 3
    assert result[0]["type"] == "STATE_TRANSITION"
    assert result[1]["type"] == "PHASE_START"
    assert result[2]["type"] == "AGENT_DONE"
    # seq must be present and ascending
    assert result[0]["seq"] < result[1]["seq"] < result[2]["seq"]
    _purge_cache(tmp_path)


def test_read_events_since_seq(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    seqs = []
    for i in range(5):
        seq = append_event(conn, "feat-b", {"type": "EV", "ts": f"t{i}", "i": i})
        seqs.append(seq)

    # since_seq = seqs[2] means we want events after index 2 (i.e. indices 3 and 4)
    result = read_events(conn, "feat-b", since_seq=seqs[2])
    assert len(result) == 2
    assert result[0]["i"] == 3
    assert result[1]["i"] == 4
    _purge_cache(tmp_path)


def test_read_last_agent_done(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    append_event(conn, "feat-c", {"type": "STATE_TRANSITION", "ts": "t1"})
    append_event(conn, "feat-c", {"type": "AGENT_DONE", "ts": "t2", "summary": "first"})
    append_event(conn, "feat-c", {"type": "PHASE_START", "ts": "t3"})
    append_event(conn, "feat-c", {"type": "AGENT_DONE", "ts": "t4", "summary": "second"})

    result = read_last_agent_done(conn, "feat-c")
    assert result is not None
    assert result["summary"] == "second"
    _purge_cache(tmp_path)


def test_read_last_agent_done_none(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    result = read_last_agent_done(conn, "feat-empty")
    assert result is None
    _purge_cache(tmp_path)


# ---------------------------------------------------------------------------
# fsm_state tests
# ---------------------------------------------------------------------------

def test_write_and_read_state(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    state = {
        "current": "BUILD",
        "rigor": "standard",
        "current_conversation": 2,
        "retry_count_by_key": {"build:1": 1},
        "iteration_by_stage": {"BUILD": 0},
        "updated_at": "2026-01-01T12:00:00Z",
        "conv_start_sha": "abc123",
        "convs_total": 4,
        "convs_done": 1,
        "build_baseline": {"tests": 413},
        "extra": {"some_future_field": True},
    }
    write_state(conn, "feat-d", state)

    result = read_state(conn, "feat-d")
    assert result is not None
    assert result["current"] == "BUILD"
    assert result["rigor"] == "standard"
    assert result["current_conversation"] == 2
    assert result["retry_count_by_key"] == {"build:1": 1}
    assert result["iteration_by_stage"] == {"BUILD": 0}
    assert result["conv_start_sha"] == "abc123"
    assert result["convs_total"] == 4
    assert result["convs_done"] == 1
    assert result["build_baseline"] == {"tests": 413}
    assert result["extra"] == {"some_future_field": True}
    _purge_cache(tmp_path)


def test_read_state_missing(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    result = read_state(conn, "nonexistent-feature")
    assert result is None
    _purge_cache(tmp_path)


# ---------------------------------------------------------------------------
# runner_state tests
# ---------------------------------------------------------------------------

def test_write_and_read_runner_state(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    runner = {
        "topic": "my-feature",
        "flow": "standard",
        "project_root": "/home/user/project",
        "model": "claude-sonnet-4-6",
        "timeout": 600,
        "run_id": "run-001",
        "status": "running",
        "current_state": "BUILD",
        "current_adapter": "claude",
        "iterations": 3,
        "max_iterations": 10,
        "cost_usd_so_far": 1.23,
        "max_cost_usd": 5.0,
        "autonomy": {"gate": "auto"},
        "pending_menu": None,
        "error_kind": None,
        "open_session": {"id": "sess-1"},
        "updated_at": "2026-01-01T12:00:00Z",
    }
    write_runner_state(conn, "feat-e", runner)

    result = read_runner_state(conn, "feat-e")
    assert result is not None
    assert result["topic"] == "my-feature"
    assert result["status"] == "running"
    assert result["current_state"] == "BUILD"
    assert result["iterations"] == 3
    assert result["cost_usd_so_far"] == pytest.approx(1.23)
    assert result["autonomy"] == {"gate": "auto"}
    assert result["open_session"] == {"id": "sess-1"}
    _purge_cache(tmp_path)


def test_mark_stale_runners(tmp_path: Path) -> None:
    conn = get_db(tmp_path)

    # Two 'running' rows and one 'done' row
    for feat, status in [("r1", "running"), ("r2", "running"), ("r3", "done")]:
        write_runner_state(conn, feat, {
            "status": status,
            "updated_at": "2026-01-01T00:00:00Z",
        })

    count = mark_stale_runners(conn)
    assert count == 2

    r1 = read_runner_state(conn, "r1")
    r2 = read_runner_state(conn, "r2")
    r3 = read_runner_state(conn, "r3")
    assert r1 is not None and r1["status"] == "error"
    assert r2 is not None and r2["status"] == "error"
    assert r3 is not None and r3["status"] == "done"
    _purge_cache(tmp_path)


# ---------------------------------------------------------------------------
# Concurrency test
# ---------------------------------------------------------------------------

def test_concurrent_appends(tmp_path: Path) -> None:
    conn = get_db(tmp_path)
    errors: list[Exception] = []

    def append_50(thread_id: int) -> None:
        try:
            for i in range(50):
                append_event(
                    conn,
                    "feat-concurrent",
                    {"type": "EV", "ts": f"t-{thread_id}-{i}", "thread": thread_id, "i": i},
                )
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    t1 = threading.Thread(target=append_50, args=(1,))
    t2 = threading.Thread(target=append_50, args=(2,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert not errors, f"Concurrent append raised: {errors}"

    rows = conn.execute(
        "SELECT seq FROM fsm_events WHERE feature='feat-concurrent' ORDER BY seq ASC"
    ).fetchall()
    assert len(rows) == 100

    # Verify no gaps in seq numbers for this feature
    seqs = [r[0] for r in rows]
    assert seqs == list(range(seqs[0], seqs[0] + 100))
    _purge_cache(tmp_path)


# ---------------------------------------------------------------------------
# Phase 8: Backward compat — legacy dirs (no pathly.db)
# ---------------------------------------------------------------------------

def test_legacy_read_state_from_json(tmp_path: Path) -> None:
    """eventlog.read_state falls back to STATE.json when no pathly.db exists."""
    import pathly_orchestrator.eventlog as eventlog

    feature_dir = tmp_path / "my-feature"
    feature_dir.mkdir()
    state = {
        "current": "BUILD",
        "rigor": "standard",
        "current_conversation": 1,
        "updated_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "STATE.json").write_text(json.dumps(state), encoding="utf-8")

    # No pathly.db — should read from STATE.json
    assert not (feature_dir / "pathly.db").exists()
    result = eventlog.read_state(str(feature_dir))
    assert result is not None
    assert result["current"] == "BUILD"
    assert result["rigor"] == "standard"
    assert result["current_conversation"] == 1


def test_legacy_read_events_from_jsonl(tmp_path: Path) -> None:
    """eventlog.read_events falls back to EVENTS.jsonl when no pathly.db exists."""
    import pathly_orchestrator.eventlog as eventlog

    feature_dir = tmp_path / "my-feature"
    feature_dir.mkdir()
    lines = [
        json.dumps({"type": "STATE_TRANSITION", "ts": "2026-01-01T00:00:01Z", "to": "BUILD", "schema_version": 1}),
        "not valid json",
        json.dumps({"type": "AGENT_DONE", "ts": "2026-01-01T00:00:02Z", "summary": "ok", "schema_version": 1}),
    ]
    (feature_dir / "EVENTS.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # No pathly.db — should read from EVENTS.jsonl; malformed line silently skipped
    assert not (feature_dir / "pathly.db").exists()
    result = eventlog.read_events(str(feature_dir))
    assert len(result) == 2
    assert result[0]["type"] == "STATE_TRANSITION"
    assert result[1]["type"] == "AGENT_DONE"


def test_recover_stale_mirrors_no_db(tmp_path: Path) -> None:
    """recover_stale_mirrors does not crash when a feature dir has no pathly.db."""
    from pathly_orchestrator.supervisor import recover_stale_mirrors

    feature_dir = tmp_path / "pathly" / "plans" / "legacy-feature"
    feature_dir.mkdir(parents=True)

    state = {"current": "BUILD", "rigor": "standard", "updated_at": "2026-01-01T00:00:00Z"}
    (feature_dir / "STATE.json").write_text(json.dumps(state), encoding="utf-8")

    lines = [json.dumps({"type": "AGENT_DONE", "ts": "2026-01-01T00:00:01Z", "summary": "s", "schema_version": 1})]
    (feature_dir / "EVENTS.jsonl").write_text("\n".join(lines), encoding="utf-8")

    # No pathly.db — should not raise
    assert not (feature_dir / "pathly.db").exists()
    recover_stale_mirrors(str(tmp_path))
