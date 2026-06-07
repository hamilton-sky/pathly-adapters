"""Health, status, and shutdown endpoints."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path

from flask import Blueprint, jsonify, request

from pathly_orchestrator.eventlog import read_state
from pathly_orchestrator.fsm_ops import build_menu_payload
from ..middleware import _metrics, _inc
from ..sse import _NO_FEATURE_MENU

logger = logging.getLogger("pathly.http")

bp = Blueprint("health", __name__)


@bp.route("/shutdown", methods=["POST"])
def shutdown():
    """Graceful shutdown — lets Studio restart with updated code."""
    threading.Timer(0.1, lambda: os._exit(0)).start()
    return jsonify({"ok": True})


@bp.route("/health", methods=["GET"])
def health():
    """Deep health check."""
    checks: dict[str, object] = {
        "status": "ok",
        "server": "pathly-fsm-http",
        "sse_clients": _metrics.get("pathly_sse_clients_active", 0),
    }
    project_root = os.environ.get("PATHLY_PROJECT_ROOT", "")
    if project_root:
        root = Path(project_root)
        checks["project_root_exists"] = root.exists()
        checks["project_root_writable"] = os.access(project_root, os.W_OK)
    return jsonify(checks), 200


@bp.route("/status", methods=["GET"])
def status_endpoint():
    """Read-only FSM state endpoint for the Studio renderer.

    Query params:
      project_root (optional): absolute path to project root;
                               falls back to PATHLY_PROJECT_ROOT env var.

    Returns JSON:
      { "current_state": str, "feature": str, "project_root": str }
    or { "current_state": "unknown" } if STATE.json not found or project_root not set.
    """
    project_root = request.args.get("project_root", "").strip()
    if not project_root:
        project_root = os.environ.get("PATHLY_PROJECT_ROOT", "").strip()

    if not project_root:
        return jsonify({"current_state": "unknown"}), 200

    resolved_root = Path(project_root).resolve()
    plans_dir = resolved_root / "pathly" / "plans"
    if not plans_dir.resolve().is_relative_to(resolved_root):
        return jsonify({"error": "Invalid project_root"}), 400
    if not plans_dir.exists():
        return jsonify({"current_state": "no-feature", "feature": "", "project_root": project_root, "menu": _NO_FEATURE_MENU}), 200

    topic = request.args.get("topic", "").strip()
    best_state: dict | None = None
    best_state_dir: Path | None = None

    if topic:
        # Specific topic requested — read directly, skip the glob.
        topic_dir = plans_dir / topic
        try:
            if not topic_dir.resolve().is_relative_to(resolved_root):
                return jsonify({"error": "Invalid topic"}), 400
        except Exception:
            return jsonify({"error": "Invalid topic"}), 400
        if topic_dir.is_dir():
            best_state = read_state(str(topic_dir))
            if best_state is not None:
                best_state_dir = topic_dir
    else:
        # Find the most recently updated STATE.json across all features.
        best_mtime: float = -1.0
        try:
            for state_file in plans_dir.glob("*/STATE.json"):
                if not state_file.resolve().is_relative_to(resolved_root):
                    continue
                try:
                    mtime = state_file.stat().st_mtime
                    if mtime > best_mtime:
                        candidate = read_state(str(state_file.parent))
                        if candidate is not None:
                            best_mtime = mtime
                            best_state = candidate
                            best_state_dir = state_file.parent
                except Exception:
                    logger.debug("status: error reading %s", state_file, exc_info=True)
        except Exception:
            logger.debug("status: error scanning plans dir", exc_info=True)
            return jsonify({"current_state": "unknown"}), 200

    if best_state is None:
        return jsonify({"current_state": "no-feature", "feature": "", "project_root": project_root, "menu": _NO_FEATURE_MENU}), 200

    # Infer feature from directory name when STATE.json lacks the field.
    feature = best_state.get("feature", "") or (best_state_dir.name if best_state_dir else "")

    menu = None
    try:
        from importlib.resources import files
        import yaml

        flow_config = yaml.safe_load(
            files("pathly_data").joinpath("core/flows/team.flow.yaml").read_text(encoding="utf-8")
        )
        storage_path = resolved_root / "pathly" / "plans" / feature
        menu = build_menu_payload(
            flow_config,
            best_state.get("current", "unknown"),
            storage_path,
        )
    except Exception:
        logger.debug("status: error building menu payload", exc_info=True)

    return jsonify(
        {
            "current_state": best_state.get("current", "unknown"),
            "feature": feature,
            "project_root": project_root,
            "menu": menu,
        }
    ), 200
