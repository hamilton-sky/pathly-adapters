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


def _run_export(
    adapter: str,
    repair: bool,
    *,
    skills: list[str] | None = None,
    all_skills: bool = False,
) -> dict:
    cmd = [sys.executable, "-m", "install_cli", adapter, "--apply"]
    if repair:
        cmd.append("--repair")
    if all_skills:
        cmd.append("--all-skills")
    for skill in skills or []:
        cmd += ["--export", skill]

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
    all_skills = bool(data.get("all_skills", False))
    skills = data.get("skills") or []

    if not adapters or not isinstance(adapters, list):
        return jsonify({"error": "'adapters' must be a non-empty list"}), 400

    if not isinstance(skills, list) or not all(isinstance(s, str) for s in skills):
        return jsonify({"error": "'skills' must be a list of skill names"}), 400

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

    results = [
        _run_export(adapter, repair, skills=skills, all_skills=all_skills)
        for adapter in adapters
    ]
    all_ok = all(r["ok"] for r in results)

    return jsonify({"ok": all_ok, "results": results})


@bp.route("/ops/export/skills", methods=["GET"])
def ops_export_skills():
    """List a host's installable skills, flagging which install by default (Tier-1).

    Powers the export panel's skill picker: only non-default skills need explicit
    selection; the Tier-1 on-ramps always install.
    """
    adapter = request.args.get("adapter", "claude")
    if adapter not in _VALID_ADAPTERS:
        return jsonify({"error": f"Unknown adapter {adapter!r}"}), 400
    try:
        import yaml  # lazy — keep import cost off the hot path
        from install_cli.orchestrate import DEFAULT_EXPOSED_SKILLS, _load_install_yaml
        from install_cli.resources import adapter_meta_path

        skills_cfg = (_load_install_yaml(adapter) or {}).get("skills") or {}
        dest = skills_cfg.get("destination")
        skills_dest = Path(dest).expanduser() if dest else None

        meta_dir = adapter_meta_path(adapter)
        skills = []
        for meta_file in sorted(meta_dir.glob("*_skill.yaml")):
            meta = yaml.safe_load(meta_file.read_text(encoding="utf-8")) or {}
            name = meta.get("skill")
            if not name:
                continue
            filename = meta.get("filename")
            installed = bool(
                skills_dest and filename and (skills_dest / filename).exists()
            )
            skills.append(
                {
                    "name": name,
                    "default": name in DEFAULT_EXPOSED_SKILLS,
                    "installed": installed,
                }
            )
        return jsonify({"adapter": adapter, "skills": skills})
    except Exception as exc:  # fail-soft — the panel degrades to on-ramps only
        logger.warning("ops_export_skills failed: %s", exc)
        return jsonify({"adapter": adapter, "skills": [], "error": str(exc)}), 200
