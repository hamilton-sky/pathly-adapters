def test_project_root_isolation():
    from pathly_orchestrator.db import get_db, append_event, read_events

    conn = get_db()
    append_event(
        conn,
        "/project/alpha",
        "security-fixes",
        {"event_type": "STAGE_CHANGE", "ts": "2026-01-01", "payload": "{}"},
    )
    events_beta = read_events(conn, "/project/beta", "security-fixes")
    assert events_beta == [], f"Cross-project bleed: {events_beta}"
    events_alpha = read_events(conn, "/project/alpha", "security-fixes")
    assert len(events_alpha) == 1


def test_get_db_reopens_connection_when_db_path_changes(tmp_path, monkeypatch):
    """A per-thread connection must follow the resolved db_path, not outlive it.

    Regression for the intermittent 'no such table' suite flake: a long-lived worker
    thread (supervisor loop / reconciliation window / embed worker) opened its
    connection against one test's db, then called get_db() again after a later test
    repatched the db path. The stale connection was reused, so get_db() migrated the
    OLD db while marking the NEW path 'prepared' — leaving the new db un-migrated for
    every later connection. This drives that exact two-connection sequence
    deterministically (event-gated, no sleeps) and asserts the new db was really built.
    """
    import sqlite3
    import threading

    import pathly_orchestrator.db.connection as conn_mod
    from pathly_orchestrator.db.connection import get_db

    db1 = tmp_path / "home1" / ".pathly" / "pathly.db"
    db2 = tmp_path / "home2" / ".pathly" / "pathly.db"
    db1.parent.mkdir(parents=True, exist_ok=True)
    db2.parent.mkdir(parents=True, exist_ok=True)

    conn_mod._prepared_paths.clear()

    go_phase1 = threading.Event()
    phase1_done = threading.Event()
    go_phase2 = threading.Event()
    phase2_done = threading.Event()
    errors: list[Exception] = []

    def worker():
        try:
            go_phase1.wait(5)
            get_db()  # opens the worker's per-thread connection against db1
            phase1_done.set()
            go_phase2.wait(5)
            get_db()  # db_path is now db2 — must reopen, not reuse the db1 connection
            phase2_done.set()
        except Exception as exc:  # pragma: no cover - surfaced via the errors list
            errors.append(exc)
            phase1_done.set()
            phase2_done.set()

    t = threading.Thread(target=worker, name="test-stale-conn-worker")
    t.start()

    monkeypatch.setenv("PATHLY_DB_PATH", str(db1))
    go_phase1.set()
    assert phase1_done.wait(5), "worker phase 1 timed out"

    monkeypatch.setenv("PATHLY_DB_PATH", str(db2))
    go_phase2.set()
    assert phase2_done.wait(5), "worker phase 2 timed out"

    t.join(5)
    assert not errors, f"worker raised: {errors!r}"

    # If the stale db1 connection had been reused, db2 would be marked prepared but
    # never migrated. A raw connection (bypassing get_db) proves the file was built.
    raw = sqlite3.connect(str(db2))
    try:
        tables = {
            r[0]
            for r in raw.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        raw.close()
    assert "fsm_events" in tables, (
        "db2 was marked prepared but never migrated — a stale per-thread connection "
        f"was reused across a db_path change. Tables present: {sorted(tables)}"
    )
