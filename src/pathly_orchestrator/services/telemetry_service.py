from pathly_orchestrator import db as _db


def get_events(project_root: str, feature: str, since_seq: int = 0) -> dict:
    conn = _db.get_db()
    events = _db.read_events(conn, project_root, feature, since_seq)
    return {"total": len(events), "events": events}


def get_event_count(project_root: str, feature: str) -> int:
    conn = _db.get_db()
    return conn.execute(
        "SELECT COUNT(*) FROM fsm_events WHERE project_root=? AND feature=?",
        (project_root, feature),
    ).fetchone()[0]


def get_spans(project_root: str, feature: str, _run_id=None) -> list[dict]:
    conn = _db.get_db()
    query = "SELECT * FROM otel_spans WHERE project_root=? AND feature=?"
    params = [project_root, feature]
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]
