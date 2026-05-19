"""Pathly FSM business logic — transport-independent."""
from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

import yaml

from pathly_orchestrator.fsm import (
    append_event,
    evaluate_transition_rules,
    recover_state,
    route_feedback,
    run_transition_actions,
    write_state,
)


# ── Private helpers ───────────────────────────────────────────────────────────

def _load_flow(flow_name: str) -> dict:
    text = files("pathly_data").joinpath(f"core/flows/{flow_name}.flow.yaml").read_text(
        encoding="utf-8"
    )
    return yaml.safe_load(text)


def _resolve_storage_path(flow_config: dict, project_root: str, topic: str) -> Path:
    template = flow_config["storage_path"]
    relative = template.format(topic=topic)
    return Path(project_root) / relative


def _load_agent_text(agent: str) -> str:
    if "/" in agent:
        return files("pathly_data").joinpath(f"core/skills/{agent}.md").read_text(
            encoding="utf-8"
        )
    return files("pathly_data").joinpath(f"core/agents/{agent}.md").read_text(
        encoding="utf-8"
    )


def build_prompt(flow_config: dict, state_name: str, storage_path: Path) -> str:
    agent = flow_config["agent_map"][state_name]
    agent_text = _load_agent_text(agent)
    context = (
        f"\n\n## Current task\n"
        f"Feature: {storage_path.name}\n"
        f"State: {state_name}\n"
        f"Storage path: {storage_path}\n"
    )
    return agent_text + context


def build_prompt_for_agent(flow_config: dict, agent_name: str, storage_path: Path) -> str:
    agent_text = _load_agent_text(agent_name)
    context = (
        f"\n\n## Current task\n"
        f"Feature: {storage_path.name}\n"
        f"Storage path: {storage_path}\n"
    )
    return agent_text + context


def _blocked_response(feedback: dict, state_info: dict) -> dict:
    if feedback["target_agent"] == "human":
        return {
            "blocked": True,
            "target_agent": "human",
            "file": feedback["file"],
            "instructions": feedback.get("instructions", ""),
            "limits": state_info["limits"],
        }
    return {
        "blocked": True,
        "target_agent": feedback["target_agent"],
        "file": feedback["file"],
        "limits": state_info["limits"],
    }


# ── Public API ────────────────────────────────────────────────────────────────

def next_action(args: dict) -> dict:
    flow_name = args["flow"]
    topic = args["topic"]
    project_root = args["project_root"]

    flow_config = _load_flow(flow_name)
    storage_path = _resolve_storage_path(flow_config, project_root, topic)

    state_info = recover_state(storage_path, flow_config)
    feedback = route_feedback(flow_config, storage_path)

    if feedback is not None:
        result = _blocked_response(feedback, state_info)
        if feedback["target_agent"] != "human":
            try:
                instructions = build_prompt_for_agent(flow_config, feedback["target_agent"], storage_path)
                result["instructions"] = instructions
            except Exception:
                result["instructions"] = None
        return result

    instructions = build_prompt(flow_config, state_info["current_state"], storage_path)
    return {
        "current_state": state_info["current_state"],
        "conv": state_info["conv"],
        "agent": flow_config["agent_map"][state_info["current_state"]],
        "instructions": instructions,
        "storage_path": str(storage_path),
        "limits": state_info["limits"],
    }


def complete_stage(args: dict) -> dict:
    flow_name = args["flow"]
    topic = args["topic"]
    project_root = args["project_root"]
    decision: str | None = args.get("decision")
    resolved_files: list[str] | None = args.get("resolved_files")

    flow_config = _load_flow(flow_name)
    storage_path = _resolve_storage_path(flow_config, project_root, topic)

    if resolved_files:
        feedback_dir = storage_path / "feedback"
        for filename in resolved_files:
            target = feedback_dir / filename
            if target.exists():
                target.unlink()
                append_event(storage_path, {"type": "FEEDBACK_RESOLVED", "file": filename})

    state_file = storage_path / "STATE.json"
    state_before: dict | None = None
    if state_file.exists():
        try:
            state_before = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state_before = None

    state_info = recover_state(storage_path, flow_config)

    feedback = route_feedback(flow_config, storage_path)
    if feedback is not None:
        result = _blocked_response(feedback, state_info)
        if feedback["target_agent"] != "human":
            try:
                instructions = build_prompt_for_agent(flow_config, feedback["target_agent"], storage_path)
                result["instructions"] = instructions
            except Exception:
                result["instructions"] = None
        return result

    if state_info["current_state"] == "DONE":
        return {"done": True}

    result = evaluate_transition_rules(flow_config, state_info["current_state"], storage_path)

    if isinstance(result, dict) and result.get("decide") is True:
        if decision is None:
            context_file = result.get("context_file", "")
            context_contents: str | None = None
            if context_file:
                ctx_path = storage_path / context_file
                if ctx_path.exists():
                    try:
                        context_contents = ctx_path.read_text(encoding="utf-8")
                    except OSError:
                        context_contents = None
            return {
                "decide": True,
                "question": result["question"],
                "context": context_contents,
                "options": result["options"],
                "default": result["default"],
            }
        else:
            options = result["options"]
            default = result["default"]
            if decision not in options:
                decision = default
            next_state = options.get(decision, options.get(default, ""))
            append_event(storage_path, {
                "type": "DECIDE_ROUTING",
                "chosen": next_state,
                "decision_input": decision,
                "options": options,
            })
    else:
        next_state = result  # type: ignore[assignment]

    if state_before is not None and state_file.exists():
        try:
            state_after = json.loads(state_file.read_text(encoding="utf-8"))
            if state_after.get("current") != state_before.get("current"):
                raise RuntimeError("STATE.json modified externally during transition")
        except (json.JSONDecodeError, OSError):
            pass

    run_transition_actions(
        flow_config,
        state_info["current_state"],
        next_state,
        storage_path,
        topic,
        state_info["conv"],
    )

    prior_state = state_before or {}
    write_state(storage_path, next_state, prior_state)

    append_event(storage_path, {
        "type": "STATE_TRANSITION",
        "from": state_info["current_state"],
        "to": next_state,
    })

    if next_state == "DONE":
        return {"done": True}

    instructions = build_prompt(flow_config, next_state, storage_path)
    return {
        "next_state": next_state,
        "agent": flow_config["agent_map"][next_state],
        "instructions": instructions,
        "limits": state_info["limits"],
    }
