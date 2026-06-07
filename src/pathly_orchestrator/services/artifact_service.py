from pathly_orchestrator import db as _db


def get_artifacts(project_root: str, feature: str) -> list[dict]:
    conn = _db.get_db()
    rows = conn.execute(
        'SELECT * FROM stage_artifacts WHERE project_root=? AND feature=?',
        (project_root, feature)
    ).fetchall()
    return [dict(r) for r in rows]
