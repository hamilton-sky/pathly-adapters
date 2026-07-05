"""FSM response-envelope and menu building — imported by fsm_compose (bottom-of-file)."""

from __future__ import annotations

import datetime
from pathlib import Path

# Imported from fsm_compose.py — safe because this module is loaded at the
# bottom of fsm_compose.py, after all those names are already defined.
from pathly_orchestrator.fsm_compose import (
    _MENU_LABELS,
    _SCHEMA_VERSION,
    _STATE_TO_COMMAND,
    _agent_hint,
    _codex_subagent_hint,
)


def _stage_brief(state_info: dict, storage_path: Path) -> dict:
    feedback_dir = storage_path / "feedback"
    open_feedback: list[str] = []
    feedback_age_hours: float | None = None

    if feedback_dir.exists():
        oldest_mtime: float | None = None
        for item in sorted(feedback_dir.iterdir()):
            if item.is_file() and item.suffix == ".md":
                open_feedback.append(item.name)
                try:
                    mtime = item.stat().st_mtime
                    if oldest_mtime is None or mtime < oldest_mtime:
                        oldest_mtime = mtime
                except OSError:
                    pass
        if oldest_mtime is not None:
            age = (datetime.datetime.now().timestamp() - oldest_mtime) / 3600
            feedback_age_hours = round(age, 1)

    recent_events: list[dict] = []
    try:
        from pathly_orchestrator import eventlog as _eventlog

        all_events = _eventlog.read_events(str(storage_path))
        recent_events = all_events[-3:] if len(all_events) >= 3 else list(all_events)
    except Exception:
        pass

    recent_consult: str | None = None
    if feedback_dir.exists():
        try:
            consult_files = sorted(
                [
                    f
                    for f in feedback_dir.iterdir()
                    if f.name.startswith("CONSULT_") and f.suffix == ".md"
                ],
                key=lambda f: f.stat().st_mtime,
                reverse=True,
            )
            if consult_files:
                recent_consult = consult_files[0].read_text(encoding="utf-8")
        except OSError:
            pass

    return {
        "state": state_info["current_state"],
        "conv": state_info["conv"],
        "retry_count": state_info.get("retry_count", 0),
        "open_feedback": open_feedback,
        "feedback_age_hours": feedback_age_hours,
        "recent_events": recent_events,
        "recent_consult": recent_consult,
        "plan_path": str(storage_path),
    }


def _exit_requirement(flow_config: dict | None, state_name: str) -> str | None:
    """Human-readable summary of what an agent must produce to advance past state_name."""
    if not flow_config or not state_name:
        return None
    lines: list[str] = []

    for key, checks in (flow_config.get("gates") or {}).items():
        if not key.startswith(f"{state_name}->"):
            continue
        target = key.split("->", 1)[1]
        for chk in checks or []:
            t = chk.get("type")
            if t == "verify_gate":
                lines.append(
                    f"Write `{chk.get('artifact')}` with its FIRST LINE exactly "
                    f"`{chk.get('pass_marker')}` (→ {target})."
                )
            elif t == "require_artifact":
                lines.append(
                    f"Produce `{chk.get('artifact')}` before advancing (→ {target})."
                )
            elif t == "scope_gate":
                lines.append(
                    f"Keep changes within the scope declared in `{chk.get('scope_file')}`."
                )

    rules = (flow_config.get("transition_rules") or {}).get(state_name) or {}
    for rule in rules.get("on_content") or []:
        lines.append(
            f"`{rule.get('file')}` must contain `{rule.get('contains')}` "
            f"(→ {rule.get('next')})."
        )

    if not lines:
        return None
    body = "\n".join(f"  - {ln}" for ln in lines)
    return f"To advance past {state_name}:\n{body}"


def _response_envelope(
    *,
    state_info: dict,
    storage_path: Path,
    agent: str,
    instructions: str | None,
    menu: dict | None,
    current_state_value: str | None = None,
    include_storage_path: bool = True,
    preferred_adapter: str = "",
    flow: dict | None = None,
) -> dict:
    state_name = current_state_value or state_info["current_state"]
    exit_req = _exit_requirement(flow, state_name)
    if exit_req and instructions:
        instructions = f"{instructions}\n\n## Exit requirement\n{exit_req}"
    brief = _stage_brief(state_info, storage_path)
    if exit_req:
        brief["exit_requirement"] = exit_req
    result = {
        "schema_version": _SCHEMA_VERSION,
        "decision": "continue",
        "current_state": state_name,
        "conv": state_info["conv"],
        "role": agent,
        "agent": agent,
        "preferred_adapter": preferred_adapter,
        "agent_hint": _agent_hint(agent, instructions),
        "stage_brief": brief,
        "warnings": [],
        "menu": menu,
    }
    if exit_req:
        result["exit_requirement"] = exit_req
    if include_storage_path:
        result["storage_path"] = str(storage_path)
    result["codex_subagent"] = _codex_subagent_hint(agent, instructions)
    if instructions is not None:
        result["instructions"] = instructions
    return result


def _blocked_response(
    feedback: dict,
    state_info: dict,
    storage_path: Path | None = None,
    preferred_adapter: str = "",
) -> dict:
    decision = "escalate" if feedback["target_agent"] == "human" else "block"
    brief = (
        _stage_brief(state_info, storage_path)
        if storage_path
        else {
            "state": state_info["current_state"],
            "conv": state_info["conv"],
            "retry_count": state_info.get("retry_count", 0),
            "open_feedback": [feedback["file"]],
            "feedback_age_hours": None,
            "recent_events": [],
            "recent_consult": None,
            "plan_path": "",
        }
    )
    warnings: list[dict] = [{"code": "open_feedback", "file": feedback["file"]}]
    age = brief.get("feedback_age_hours")
    if age is not None and age >= 4:
        warnings.append(
            {
                "code": "feedback_stale",
                "file": feedback["file"],
                "age_hours": age,
                "message": f"{feedback['file']} has been open for {age}h — review before continuing.",
            }
        )
    result = {
        "schema_version": _SCHEMA_VERSION,
        "decision": decision,
        "current_state": state_info["current_state"],
        "conv": state_info["conv"],
        "role": feedback["target_agent"],
        "agent": feedback["target_agent"],
        "preferred_adapter": preferred_adapter,
        "agent_hint": _agent_hint(
            feedback["target_agent"], feedback.get("instructions")
        ),
        "stage_brief": brief,
        "warnings": warnings,
        "limits": state_info["limits"],
        "storage_path": str(storage_path) if storage_path else "",
        "blocked": True,
        "target_agent": feedback["target_agent"],
        "file": feedback["file"],
    }
    if feedback["target_agent"] == "human":
        result["instructions"] = feedback.get("instructions", "")
    return result


def build_menu_payload(flow_config: dict, state_name: str, storage_path: Path) -> dict:
    transitions = flow_config.get("transitions") or {}
    transition_rules = flow_config.get("transition_rules") or {}
    targets = list(transitions.get(state_name, []))
    agent = flow_config.get("agent_map", {}).get(state_name, "")
    items: list[dict] = []

    rule = transition_rules.get(state_name)
    if isinstance(rule, dict):
        decide = rule.get("decide")
        if isinstance(decide, dict):
            options = decide.get("options", {}) or {}
            for label, target in options.items():
                items.append(
                    {
                        "label": str(label),
                        "description": f"Route to {target}",
                        "command": str(label),
                        "target_state": str(target),
                        "terminal_kind": "claude",
                    }
                )

    if not items:
        for target in targets:
            items.append(
                {
                    "label": target,
                    "description": _MENU_LABELS.get(target, f"Advance to {target}."),
                    "command": _STATE_TO_COMMAND.get(
                        target, f"/pathly {target.lower()}"
                    ),
                    "target_state": target,
                    "terminal_kind": "claude",
                }
            )

    return {
        "state": state_name,
        "feature": storage_path.name,
        "agent": agent,
        "title": f"Pathly · {storage_path.name} · {state_name}",
        "subtitle": _MENU_LABELS.get(state_name, ""),
        "items": items,
        "empty_message": "No menu items available for this state.",
    }
