"""Pathly FSM MCP server.

Zero external dependencies — implements the MCP stdio protocol (JSON-RPC 2.0
with Content-Length framing) directly. Works with Claude Code and Codex.

Run via:  pathly-fsm
"""
from __future__ import annotations

import json
import sys
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

_MAX_BODY = 1_048_576  # 1 MiB

_TOOLS = [
    {
        "name": "next_action",
        "description": (
            "Return the next action for the FSM: the current state, agent instructions, "
            "and any blocked feedback that must be resolved first."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "flow": {
                    "type": "string",
                    "description": "Flow name (e.g. 'team'). Resolves to core/flows/<flow>.flow.yaml.",
                },
                "topic": {
                    "type": "string",
                    "description": "Feature or topic name (used to format storage_path).",
                },
                "project_root": {
                    "type": "string",
                    "description": "Absolute path to the project root directory.",
                },
            },
            "required": ["flow", "topic", "project_root"],
        },
    },
    {
        "name": "complete_stage",
        "description": (
            "Advance the FSM to the next state after the current stage is done. "
            "Handles decide-blocks, transition actions, and state persistence."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "flow": {
                    "type": "string",
                    "description": "Flow name (e.g. 'team').",
                },
                "topic": {
                    "type": "string",
                    "description": "Feature or topic name.",
                },
                "project_root": {
                    "type": "string",
                    "description": "Absolute path to the project root directory.",
                },
                "decision": {
                    "type": "string",
                    "description": "Decision key chosen from a decide-block options dict (Call 2 only).",
                },
                "resolved_files": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Feedback filenames (with .md) that have been resolved and should be deleted.",
                },
            },
            "required": ["flow", "topic", "project_root"],
        },
    },
]


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
    # Agents with "/" (e.g. "team/build") live in core/skills/.
    # Top-level agents (e.g. "builder") live in core/agents/.
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


# ── Tool handlers ─────────────────────────────────────────────────────────────

def _next_action(args: dict) -> dict:
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


def _complete_stage(args: dict) -> dict:
    flow_name = args["flow"]
    topic = args["topic"]
    project_root = args["project_root"]
    decision: str | None = args.get("decision")
    resolved_files: list[str] | None = args.get("resolved_files")

    flow_config = _load_flow(flow_name)
    storage_path = _resolve_storage_path(flow_config, project_root, topic)

    # Step 2: resolve feedback files
    if resolved_files:
        feedback_dir = storage_path / "feedback"
        for filename in resolved_files:
            target = feedback_dir / filename
            if target.exists():
                target.unlink()
                append_event(storage_path, {"type": "FEEDBACK_RESOLVED", "file": filename})

    # Step 3: read STATE.json for concurrent-write guard
    state_file = storage_path / "STATE.json"
    state_before: dict | None = None
    if state_file.exists():
        try:
            state_before = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state_before = None

    # Step 4: recover state
    state_info = recover_state(storage_path, flow_config)

    # Step 5: route feedback
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

    # Step 7: check DONE
    if state_info["current_state"] == "DONE":
        return {"done": True}

    # Step 8: evaluate transition rules
    result = evaluate_transition_rules(flow_config, state_info["current_state"], storage_path)

    # Step 9: handle decide sentinel
    if isinstance(result, dict) and result.get("decide") is True:
        if decision is None:
            # Call 1: return decide prompt
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
            # Call 2: resolve decision
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

    # Step 11: concurrent-write guard
    if state_before is not None and state_file.exists():
        try:
            state_after = json.loads(state_file.read_text(encoding="utf-8"))
            if state_after.get("current") != state_before.get("current"):
                raise RuntimeError("STATE.json modified externally during transition")
        except (json.JSONDecodeError, OSError):
            pass

    # Step 12: run transition actions
    run_transition_actions(
        flow_config,
        state_info["current_state"],
        next_state,
        storage_path,
        topic,
        state_info["conv"],
    )

    # Step 13: write state
    prior_state = state_before or {}
    write_state(storage_path, next_state, prior_state)

    # Step 14: append event
    append_event(storage_path, {
        "type": "STATE_TRANSITION",
        "from": state_info["current_state"],
        "to": next_state,
    })

    # Step 15: check DONE
    if next_state == "DONE":
        return {"done": True}

    # Step 16-17: build instructions and return
    instructions = build_prompt(flow_config, next_state, storage_path)
    return {
        "next_state": next_state,
        "agent": flow_config["agent_map"][next_state],
        "instructions": instructions,
        "limits": state_info["limits"],
    }


# ── MCP wire protocol ─────────────────────────────────────────────────────────

def _send(obj: dict) -> None:
    body = json.dumps(obj)
    encoded = body.encode("utf-8")
    header = f"Content-Length: {len(encoded)}\r\n\r\n"
    sys.stdout.buffer.write(header.encode("utf-8") + encoded)
    sys.stdout.buffer.flush()


def _read_message() -> dict | None:
    stdin = sys.stdin.buffer
    headers: dict[str, str] = {}

    while True:
        raw = stdin.readline()
        if not raw:
            return None  # EOF
        line = raw.decode("utf-8").strip()
        if not line:
            break  # blank line ends headers
        if ":" in line:
            key, _, val = line.partition(":")
            headers[key.strip().lower()] = val.strip()

    try:
        length = int(headers.get("content-length", 0))
    except ValueError:
        return None
    if length < 0 or length > _MAX_BODY:
        return None
    if not length:
        return None

    body = stdin.read(length).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _handle(req: dict) -> dict | None:
    rid = req.get("id")
    method = req.get("method", "")
    params = req.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pathly-fsm", "version": "0.1.0"},
            },
        }

    if method == "notifications/initialized":
        return None  # notification — no response

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": _TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}

        if name == "next_action":
            try:
                result = _next_action(args)
            except Exception as exc:
                result = {"error": str(exc)}
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
            }

        if name == "complete_stage":
            try:
                result = _complete_stage(args)
            except Exception as exc:
                result = {"error": str(exc)}
            return {
                "jsonrpc": "2.0",
                "id": rid,
                "result": {"content": [{"type": "text", "text": json.dumps(result)}]},
            }

        return {
            "jsonrpc": "2.0",
            "id": rid,
            "error": {"code": -32601, "message": f"Unknown tool: {name}"},
        }

    # Notifications have no id — swallow silently
    if rid is None:
        return None

    return {
        "jsonrpc": "2.0",
        "id": rid,
        "error": {"code": -32601, "message": f"Unknown method: {method}"},
    }


def run() -> None:
    while True:
        msg = _read_message()
        if msg is None:
            break
        response = _handle(msg)
        if response is not None:
            _send(response)


def main() -> None:
    run()


if __name__ == "__main__":
    main()
