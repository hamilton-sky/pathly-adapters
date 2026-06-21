from pathly_orchestrator import db as _db


def record_skill_override(
    project_root: str, feature: str, run_id, stage: str, skill_name: str
) -> None:
    conn = _db.get_db()
    _db.write_skill_override(conn, project_root, feature, run_id, stage, skill_name)


def get_invocations(project_root: str, feature: str) -> list[dict]:
    conn = _db.get_db()
    return _db.read_agent_invocations(conn, project_root, feature)


def get_agents(project_root=None) -> list[dict]:
    conn = _db.get_db()
    return _db.read_agent_definitions(conn, project_root)


def get_skills(project_root=None) -> list[dict]:
    conn = _db.get_db()
    return _db.read_skill_definitions(conn, project_root)


def resolve_skill(skill_name: str, project_root=None) -> dict | None:
    conn = _db.get_db()
    if project_root is not None:
        row = conn.execute(
            """SELECT * FROM skill_definitions
               WHERE skill=? AND (project_root=? OR project_root IS NULL)
               ORDER BY project_root IS NULL
               LIMIT 1""",
            (skill_name, project_root),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM skill_definitions WHERE skill=? AND project_root IS NULL LIMIT 1",
            (skill_name,),
        ).fetchone()
    return dict(row) if row else None
