from pathly_orchestrator import db as _db


def get_feature_list(project_root: str) -> list[dict]:
    conn = _db.get_db()
    rows = conn.execute(
        "SELECT DISTINCT feature FROM fsm_state WHERE project_root=?", (project_root,)
    ).fetchall()
    result = []
    for row in rows:
        feature = row[0]
        state = _db.read_state(conn, project_root, feature) or {}
        result.append(
            {
                "feature": feature,
                "project_root": project_root,
                "last_state": state.get("current_state"),
                "updated_at": state.get("updated_at"),
            }
        )
    return result


def get_flows(project_root=None) -> list[dict]:
    conn = _db.get_db()
    return _db.read_flow_definitions(conn, project_root)


def get_flow(flow_name: str) -> dict | None:
    conn = _db.get_db()
    rows = _db.read_flow_definitions(conn)
    return next((r for r in rows if r["name"] == flow_name), None)


def save_flow(flow_dict: dict) -> None:
    conn = _db.get_db()
    _db.upsert_flow_definition(
        conn,
        flow_dict.get("project_root"),
        flow_dict["name"],
        flow_dict.get("version", "1"),
        flow_dict.get("flow_yaml", ""),
    )
