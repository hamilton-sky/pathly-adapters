"""Adapter export endpoint — POST /ops/export."""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request

logger = logging.getLogger("pathly.http")
bp = Blueprint("export", __name__)

_VALID_ADAPTERS = {"claude", "codex", "copilot", "antigravity"}
_EXPORT_TIMEOUT = 120


def _project_root() -> str:
    return os.environ.get("PATHLY_PROJECT_ROOT", "") or str(
        Path(__file__).parent.parent.parent.parent.parent.parent
    )


def _run_export(adapter: str, repair: bool) -> dict:
    cmd = [sys.executable, "-m", "install_cli", adapter, "--apply"]
    if repair:
        cmd.append("--repair")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=_EXPORT_TIMEOUT,
            cwd=_project_root(),
        )
        combined = (result.stdout + result.stderr).strip()
        tail = "\n".join(combined.splitlines()[-30:]) if combined else ""
        return {
            "adapter": adapter,
            "ok": result.returncode == 0,
            "summary": tail,
            "exit_code": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {
            "adapter": adapter,
            "ok": False,
            "summary": f"Timed out after {_EXPORT_TIMEOUT}s",
            "exit_code": -1,
        }
    except Exception as exc:
        return {
            "adapter": adapter,
            "ok": False,
            "summary": str(exc),
            "exit_code": -1,
        }


@bp.route("/ops/export", methods=["POST"])
def ops_export():
    """Export Pathly skills/agents to one or more CLI adapters on demand."""
    data = request.get_json(silent=True) or {}
    adapters = data.get("adapters")
    repair = bool(data.get("repair", True))

    if not adapters or not isinstance(adapters, list):
        return jsonify({"error": "'adapters' must be a non-empty list"}), 400

    unknown = [a for a in adapters if a not in _VALID_ADAPTERS]
    if unknown:
        return (
            jsonify(
                {
                    "error": f"Unknown adapter(s): {unknown}. "
                    f"Valid: {sorted(_VALID_ADAPTERS)}"
                }
            ),
            400,
        )

    results = [_run_export(adapter, repair) for adapter in adapters]
    all_ok = all(r["ok"] for r in results)

    return jsonify({"ok": all_ok, "results": results})
