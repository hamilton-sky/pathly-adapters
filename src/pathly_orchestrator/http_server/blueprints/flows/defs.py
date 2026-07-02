"""Flow definition CRUD endpoints."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml
from flask import Blueprint, jsonify, request

bp = Blueprint("flows", __name__)


@bp.route("/flows/", methods=["GET"])
@bp.route("/flows", methods=["GET"])
def list_flows():
    """Return all flow definitions as a list."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_definitions

        conn = get_db()
        flows = read_flow_definitions(conn, project_root=None)
        result = [
            {
                "name": f["name"],
                "file_path": (f.get("file_path") or "").replace("\\", "/"),
                "updated_at": f.get("updated_at", ""),
            }
            for f in flows
        ]
        return jsonify(result), 200
    except Exception as e:
        logging.exception("list_flows error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<name>/graph", methods=["GET"])
def get_flow_graph(name: str):
    """Return a flow's structure as a parsed JSON object (assembled from rows).
    Response: { "graph": <FlowYaml-shaped dict>, "name": str }
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import (
            _assemble_flow_dict,
            read_flow_by_name,
            read_flow_nodes,
        )

        conn = get_db()
        row = read_flow_by_name(conn, name)
        if not row:
            return jsonify({"error": f"Flow '{name}' not found"}), 404

        node_rows = read_flow_nodes(conn, row["id"])
        if not node_rows:
            import yaml as _yaml

            graph = _yaml.safe_load(row["flow_yaml"])
        else:
            flow_level_config = json.loads(row.get("config_json") or "{}")
            graph = _assemble_flow_dict(conn, row["id"], flow_level_config)

        return jsonify({"graph": graph, "name": name}), 200
    except Exception as e:
        logging.exception("get_flow_graph error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<name>/graph", methods=["PUT"])
def update_flow_graph(name: str):
    """Replace a flow's nodes+edges from a structured graph JSON payload.
    Body: { "graph": <FlowYaml-shaped dict> }
    Effect (one write-lock, one commit):
      - upsert flow_definitions (re-serialized flow_yaml cache + config_json)
      - replace-all flow_nodes / flow_edges
      - write-through .flow.yaml to disk
    Returns: { "ok": true }
    """
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import (
            read_flow_by_name,
            upsert_flow_definition,
        )

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
        graph = data.get("graph")
        if not graph or not isinstance(graph, dict):
            return jsonify({"error": "Missing or invalid 'graph' key"}), 400

        flow_yaml = yaml.dump(graph, allow_unicode=True, sort_keys=False)

        conn = get_db()
        existing = read_flow_by_name(conn, name)
        file_path = (existing.get("file_path") or "") if existing else ""

        upsert_flow_definition(
            conn,
            project_root=None,
            name=name,
            version="",
            flow_yaml=flow_yaml,
            file_path=file_path,
        )

        if file_path:
            try:
                Path(file_path.replace("/", "\\")).write_text(
                    flow_yaml, encoding="utf-8"
                )
            except Exception:
                pass

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("update_flow_graph error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<path:name>", methods=["GET"])
def get_flow(name: str):
    """Return a flow definition by name."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_by_name

        conn = get_db()
        flow = read_flow_by_name(conn, name)
        if not flow:
            return jsonify({"error": f"Flow '{name}' not found"}), 404
        return (
            jsonify(
                {
                    "name": flow["name"],
                    "flow_yaml": flow["flow_yaml"],
                    "file_path": (flow.get("file_path") or "").replace("\\", "/"),
                    "updated_at": flow.get("updated_at", ""),
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("get_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<path:name>", methods=["PUT"])
def update_flow(name: str):
    """Update a flow's YAML content in DB and write-through to disk."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import (
            read_flow_by_name,
            upsert_flow_definition,
        )

        conn = get_db()
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400
        flow_yaml = data.get("flow_yaml", "")
        existing = read_flow_by_name(conn, name)
        file_path = (existing.get("file_path") or "") if existing else ""
        upsert_flow_definition(
            conn,
            project_root=None,
            name=name,
            version="",
            flow_yaml=flow_yaml,
            file_path=file_path,
        )
        if file_path:
            try:
                Path(file_path.replace("/", "\\")).write_text(
                    flow_yaml, encoding="utf-8"
                )
            except Exception:
                pass
        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("update_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/new", methods=["POST"])
def create_flow():
    """Create a new .flow.yaml file from a name template.
    Body: {"name": "my-flow"}
    Returns: {"name": "my-flow", "file_path": "...", "flow_yaml": "..."}
    """
    try:
        import re as _re
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import upsert_flow_definition
        from pathly_orchestrator.db.queries.catalog_items import _find_data_root

        data = request.get_json() or {}
        name = data.get("name", "").strip()
        if not name:
            return jsonify({"error": "Field 'name' is required"}), 400
        name = _re.sub(r"[^a-z0-9\-]", "-", name.lower()).strip("-")
        if not name:
            return jsonify({"error": "Invalid name"}), 400

        data_root = _find_data_root()
        if not data_root:
            return jsonify({"error": "Cannot locate pathly_data"}), 500

        flows_dir = data_root / "core" / "flows"
        flows_dir.mkdir(parents=True, exist_ok=True)
        file_path = flows_dir / f"{name}.flow.yaml"

        if file_path.exists():
            return jsonify({"error": f"Flow '{name}' already exists"}), 409

        flow_yaml = f"""---

---
version: 1
flow: {name}
storage_path: "pathly/features/{{topic}}/"
states:
  - STORMING
  - PLANNING
  - BUILDING
  - DONE
transitions:
  STORMING:
    - PLANNING
  PLANNING:
    - BUILDING
  BUILDING:
    - DONE
"""
        file_path.write_text(flow_yaml, encoding="utf-8")
        conn = get_db()
        upsert_flow_definition(
            conn,
            project_root=None,
            name=name,
            version="1",
            flow_yaml=flow_yaml,
            file_path=str(file_path).replace("\\", "/"),
        )
        return (
            jsonify(
                {
                    "name": name,
                    "file_path": str(file_path).replace("\\", "/"),
                    "flow_yaml": flow_yaml,
                }
            ),
            201,
        )
    except Exception as e:
        logging.exception("create_flow error")
        return jsonify({"error": str(e)}), 500


@bp.route("/flows/<path:name>", methods=["DELETE"])
def delete_flow(name: str):
    """Delete a flow from DB and disk."""
    try:
        from pathly_orchestrator.db import get_db
        from pathly_orchestrator.db.queries.flow_defs import read_flow_by_name
        from pathly_orchestrator.db.connection import _get_write_lock

        conn = get_db()
        flow = read_flow_by_name(conn, name)
        if not flow:
            return jsonify({"error": f"Flow '{name}' not found"}), 404

        with _get_write_lock(conn):
            conn.execute(
                "DELETE FROM flow_definitions WHERE name=? AND project_root IS NULL",
                (name,),
            )
            conn.commit()

        file_path = (flow.get("file_path") or "").replace("/", "\\")
        if file_path:
            try:
                Path(file_path).unlink(missing_ok=True)
            except Exception:
                pass

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("delete_flow error")
        return jsonify({"error": str(e)}), 500
