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
