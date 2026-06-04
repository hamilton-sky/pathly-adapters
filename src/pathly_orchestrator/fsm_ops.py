"""Pathly FSM business logic — transport-independent."""

from __future__ import annotations

import datetime
import json
import logging
import re
import subprocess
from importlib.resources import files
from pathlib import Path

import yaml

from pathly_orchestrator.fsm import (
    append_event,
    evaluate_transition_rules,
    recover_state,
    route_feedback,
    run_gates,
    run_transition_actions,
    write_state,
)

_AGENT_GROUPS = {
    "architect": "planning",
    "builder": "building",
    "designer": "building",
    "explorer": "research",
    "orchestrator": "support",
    "planner": "planning",
    "po": "planning",
    "quick": "support",
    "reviewer": "quality",
    "scout": "research",
    "tester": "quality",
    "web-researcher": "research",
}

_CODEX_EXPLORER_AGENTS = {"explorer", "quick", "scout", "web-researcher"}

_MENU_LABELS = {
    "STORMING": "Refine the idea and choose the first planning step.",
    "PLANNING": "Draft or revise the implementation plan.",
    "DESIGNING": "Shape the UI or flow design before building.",
    "BUILDING": "Implement the current plan.",
    "REVIEWING": "Review the build and decide whether to loop back.",
    "TESTING": "Verify the feature and capture failures if any.",
    "RETRO": "Close out the feature and capture lessons.",
    "DONE": "Feature complete.",
}

_STATE_TO_COMMAND = {
    "STORMING": "/pathly storm",
    "PLANNING": "/pathly plan",
    "DESIGNING": "/pathly design",
    "BUILDING": "/pathly build",
    "REVIEWING": "/pathly review",
    "TESTING": "/pathly test",
    "RETRO": "/pathly retro",
    "DONE": "/pathly end",
}

_SCHEMA_VERSION = "1"

# ── Private helpers ───────────────────────────────────────────────────────────


def _load_flow(flow_name: str) -> dict:
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow_name}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    return yaml.safe_load(text)


def _resolve_storage_path(flow_config: dict, project_root: str, topic: str) -> Path:
    template = flow_config["storage_path"]
    relative = template.format(topic=topic)
    return Path(project_root) / relative


def _load_agent_text(agent: str) -> str:
    if "/" in agent:
        return (
            files("pathly_data")
            .joinpath(f"core/skills/{agent}.md")
            .read_text(encoding="utf-8")
        )
    group = _AGENT_GROUPS.get(agent)
    relative_path = (
        f"core/agents/{group}/{agent}.md" if group else f"core/agents/{agent}.md"
    )
    return (
        files("pathly_data")
        .joinpath(relative_path)
        .read_text(encoding="utf-8")
    )


_SKILL_AGENT_ROLE: dict[str, str] = {
    "team/build": "builder",
    "team/review": "reviewer",
    "team/test": "tester",
    "team/plan": "planner",
    "team/design": "designer",
    "team/retro": "planner",
}


def _inject_prompt_vars(text: str, feature: str, project_root: str, agent_role: str, storage_path: Path | None = None) -> str:
    """Replace log-phase markers and common placeholders with real values.

    Converts bare `log-phase PHASE_START <phase>` lines into executable bash
    commands so agents actually run them instead of treating them as annotations.
    Also substitutes <feature>, <project_root>, <agent>, and <feature_path>
    placeholders that appear in the progress-logging and completion-report fragments.
    """

    def _make_log_phase_cmd(m: re.Match) -> str:  # type: ignore[type-arg]
        event_type = m.group(1)
        phase = m.group(2)
        return (
            f"Run:\n"
            f"```bash\n"
            f'pathly-fsm-call record-phase --feature "{feature}" --agent "{agent_role}"'
            f' --phase "{phase}" --event-type {event_type}'
            f' --project-root "{project_root}"\n'
            f"```\n"
            f"_(skip silently if unavailable)_"
        )

    text = re.sub(
        r"^log-phase (PHASE_START|PHASE_DONE) (\w+)\s*$",
        _make_log_phase_cmd,
        text,
        flags=re.MULTILINE,
    )
    text = text.replace("<feature>", feature)
    text = text.replace("<project_root>", project_root)
    text = text.replace("<agent>", agent_role)
    if storage_path is not None:
        feature_path = storage_path.as_posix().rstrip("/")
        text = text.replace("<feature_path>", feature_path)
    return text


def build_prompt(flow_config: dict, state_name: str, storage_path: Path) -> str:
    agent = flow_config["agent_map"][state_name]
    feature = storage_path.name
    project_root = str(storage_path.parent.parent.parent)
    _role = _SKILL_AGENT_ROLE.get(agent)
    agent_role: str = _role if _role is not None else (agent.split("/")[-1] if "/" in agent else agent)

    if "/" in agent:
        # Stage skill — compose fragments for the live adapter. Skills absent from
        # the composition manifest are returned raw, so this is a no-op until converted.
        from pathly_orchestrator.compose import compose_skill, compose_skill_with_block

        adapter = _resolve_adapter(flow_config, state_name) or "claude"
        composition = flow_config.get("composition", {})
        block_name = composition.get(state_name)
        if block_name:
            try:
                agent_text = compose_skill_with_block(agent, block_name, adapter)
            except KeyError:
                logging.getLogger(__name__).warning(
                    "composition-blocks: unknown block %r for state %r — falling back to compose_skill",
                    block_name, state_name
                )
                agent_text = compose_skill(agent, adapter)
        else:
            agent_text = compose_skill(agent, adapter)
    else:
        agent_text = _load_agent_text(agent)

    agent_text = _inject_prompt_vars(agent_text, feature, project_root, agent_role, storage_path=storage_path)

    context = (
        f"\n\n## Current task\n"
        f"Feature: {feature}\n"
        f"State: {state_name}\n"
        f"Storage path: {storage_path}\n"
    )
    from pathly_orchestrator.runner import build_pipeline_history_block
    import os
    events_path = os.path.join(project_root, "pathly", "plans", feature, "EVENTS.jsonl")
    history = build_pipeline_history_block(events_path)
    return agent_text + context + history


def build_prompt_for_agent(
    flow_config: dict,  # noqa: ARG001 — kept for call-site compat
    agent_name: str,
    storage_path: Path,
) -> str:
    agent_text = _load_agent_text(agent_name)
    context = (
        f"\n\n## Current task\n"
        f"Feature: {storage_path.name}\n"
        f"Storage path: {storage_path}\n"
    )
    return agent_text + context


def _codex_subagent_hint(agent: str, instructions: str | None) -> dict:
    codex_role = "explorer" if agent in _CODEX_EXPLORER_AGENTS else "worker"
    prompt = (
        f"PATHLY AGENT: {agent}\n"
        f"CODEX FALLBACK ROLE: {codex_role}\n\n"
        "Use the Pathly role instructions below as the source of truth. "
        "Preserve the requested artifacts, limits, and completion signal. "
        "Do not revert unrelated user changes.\n\n"
    )
    if instructions:
        prompt += instructions
    else:
        prompt += "No role instructions were available. Report this as a Pathly routing issue."
    return {
        "pathly_agent": agent,
        "codex_role": codex_role,
        "mode": "native-pathly-agent-if-callable-else-codex-role",
        "instructions": prompt,
    }


def _agent_hint(agent: str, instructions: str | None) -> dict:
    codex_role = "explorer" if agent in _CODEX_EXPLORER_AGENTS else "worker"
    prompt = (
        f"PATHLY AGENT: {agent}\n"
        f"CODEX FALLBACK ROLE: {codex_role}\n\n"
        "Use the Pathly role instructions below as the source of truth. "
        "Preserve the requested artifacts, limits, and completion signal. "
        "Do not revert unrelated user changes.\n\n"
    )
    if instructions:
        prompt += instructions
    else:
        prompt += "No role instructions were available. Report this as a Pathly routing issue."
    return {
        "agent": agent,
        "role": codex_role,
        "mode": "native-pathly-agent-if-callable-else-codex-role",
        "instructions": prompt,
    }


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

    # 1.1 — last 3 EVENTS.jsonl entries for agent context
    recent_events: list[dict] = []
    events_file = storage_path / "EVENTS.jsonl"
    if events_file.exists():
        try:
            lines = [ln for ln in events_file.read_text(encoding="utf-8").splitlines() if ln.strip()]
            for line in lines[-3:]:
                try:
                    recent_events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except OSError:
            pass

    # 1.3 — most recent CONSULT_*.md for meet.md auto-injection
    recent_consult: str | None = None
    if feedback_dir.exists():
        try:
            consult_files = sorted(
                [f for f in feedback_dir.iterdir() if f.name.startswith("CONSULT_") and f.suffix == ".md"],
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
        "feedback_age_hours": feedback_age_hours,  # 1.4 — TTL visibility
        "recent_events": recent_events,
        "recent_consult": recent_consult,
        "plan_path": str(storage_path),
    }


def _resolve_adapter(flow_config: dict, state_name: str) -> str:
    # slot reserved: per-feature STATE.json override (follow-up work)
    adapter_map = flow_config.get("adapter_map") or {}
    return adapter_map.get(state_name) or adapter_map.get("default") or ""


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
) -> dict:
    result = {
        "schema_version": _SCHEMA_VERSION,
        "decision": "continue",
        "current_state": current_state_value or state_info["current_state"],
        "conv": state_info["conv"],
        "role": agent,
        "agent": agent,
        "preferred_adapter": preferred_adapter,
        "agent_hint": _agent_hint(agent, instructions),
        "stage_brief": _stage_brief(state_info, storage_path),
        "warnings": [],
        "menu": menu,
    }
    if include_storage_path:
        result["storage_path"] = str(storage_path)
    result["codex_subagent"] = _codex_subagent_hint(agent, instructions)
    if instructions is not None:
        result["instructions"] = instructions
    return result


def _blocked_response(feedback: dict, state_info: dict, storage_path: Path | None = None, preferred_adapter: str = "") -> dict:
    decision = "escalate" if feedback["target_agent"] == "human" else "block"
    brief = _stage_brief(state_info, storage_path) if storage_path else {
        "state": state_info["current_state"],
        "conv": state_info["conv"],
        "retry_count": state_info.get("retry_count", 0),
        "open_feedback": [feedback["file"]],
        "feedback_age_hours": None,
        "recent_events": [],
        "recent_consult": None,
        "plan_path": "",
    }
    warnings: list[dict] = [{"code": "open_feedback", "file": feedback["file"]}]
    age = brief.get("feedback_age_hours")
    if age is not None and age >= 4:
        warnings.append({"code": "feedback_stale", "file": feedback["file"], "age_hours": age,
                         "message": f"⚠ {feedback['file']} has been open for {age}h — review before continuing."})
    result = {
        "schema_version": _SCHEMA_VERSION,
        "decision": decision,
        "current_state": state_info["current_state"],
        "conv": state_info["conv"],
        "role": feedback["target_agent"],
        "agent": feedback["target_agent"],
        "preferred_adapter": preferred_adapter,
        "agent_hint": _agent_hint(feedback["target_agent"], feedback.get("instructions")),
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
                    "command": _STATE_TO_COMMAND.get(target, f"/pathly {target.lower()}"),
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


# ── Public API ────────────────────────────────────────────────────────────────


def _count_planned_convs(storage_path: Path) -> int:
    """Count unique conversation numbers in the # column of PROGRESS.md."""
    progress_file = storage_path / "PROGRESS.md"
    if not progress_file.exists():
        return 0
    try:
        text = progress_file.read_text(encoding="utf-8")
    except OSError:
        return 0
    numbers: set[str] = set()
    for line in text.splitlines():
        m = re.match(r"^\s*\|\s*(\d+)\s*\|", line)
        if m:
            numbers.add(m.group(1))
    return len(numbers)


def _get_head_sha(project_root: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


def next_action(args: dict) -> dict:
    flow_name = args["flow"]
    topic = args["topic"]
    project_root = args["project_root"]

    flow_config = _load_flow(flow_name)
    storage_path = _resolve_storage_path(flow_config, project_root, topic)

    try:
        state_info = recover_state(storage_path, flow_config)
    except Exception as e:
        return {
            "schema_version": _SCHEMA_VERSION,
            "decision": "escalate",
            "current_state": "UNKNOWN",
            "conv": 0,
            "role": "human",
            "agent": "human",
            "agent_hint": {"agent": "human", "role": "human", "mode": "escalate", "instructions": "FSM state is corrupt or unreadable. Human intervention required."},
            "stage_brief": {"state": "UNKNOWN", "conv": 0, "retry_count": 0, "open_feedback": [], "feedback_age_hours": None, "recent_events": [], "recent_consult": None, "plan_path": ""},
            "warnings": [{"code": "corrupt_state", "message": str(e)}],
            "blocked": True,
            "target_agent": "human",
            "file": "HUMAN_QUESTIONS.md",
            "instructions": f"FSM state recovery failed: {e}",
            "storage_path": str(storage_path),
        }

    state_file = storage_path / "STATE.json"
    prior_state: dict = {}
    if state_file.exists():
        try:
            prior_state = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            prior_state = {}

    stamped_state = dict(prior_state)
    needs_write = False

    if not prior_state.get("conv_start_sha"):
        stamped_state["conv_start_sha"] = _get_head_sha(project_root)
        needs_write = True

    if state_info["current_state"] == "BUILDING" and not prior_state.get("build_baseline"):
        try:
            dirty_run = subprocess.run(
                ["git", "status", "--porcelain=v1"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            dirty_paths = sorted(set(
                line[3:].strip()
                for line in dirty_run.stdout.splitlines()
                if line.strip()
            )) if dirty_run.returncode == 0 else []
        except Exception:
            dirty_paths = []
        truncated = len(dirty_paths) > 500
        if truncated:
            dirty_paths = dirty_paths[:500]
        baseline: dict = {
            "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "preexisting_dirty": dirty_paths,
        }
        if truncated:
            baseline["truncated"] = True
        stamped_state["build_baseline"] = baseline
        needs_write = True

    if stamped_state.get("convs_total") is None:
        total = _count_planned_convs(storage_path)
        stamped_state["convs_total"] = total
        stamped_state["convs_done"] = 0
        needs_write = True
    else:
        current_total = _count_planned_convs(storage_path)
        if current_total != stamped_state.get("convs_total"):
            append_event(
                storage_path,
                {
                    "type": "WARNING",
                    "reason": "convs_total_mismatch",
                    "persisted": stamped_state.get("convs_total"),
                    "current": current_total,
                },
            )

    if needs_write:
        write_state(storage_path, state_info["current_state"], stamped_state)
        prior_state = stamped_state

    feedback = route_feedback(flow_config, storage_path)

    if feedback is not None:
        result = _blocked_response(feedback, state_info, storage_path,
                                   preferred_adapter=_resolve_adapter(flow_config, state_info["current_state"]))
        if feedback["target_agent"] != "human":
            try:
                instructions = build_prompt_for_agent(
                    flow_config, feedback["target_agent"], storage_path
                )
                result["instructions"] = instructions
                result["agent_hint"] = _agent_hint(feedback["target_agent"], instructions)
                result["codex_subagent"] = _codex_subagent_hint(feedback["target_agent"], instructions)
            except Exception:
                result["instructions"] = None
        return result

    # Terminal state — no agent to dispatch to
    if state_info["current_state"] == "DONE":
        return {"done": True}

    instructions = build_prompt(flow_config, state_info["current_state"], storage_path)
    agent = flow_config["agent_map"][state_info["current_state"]]
    menu = build_menu_payload(flow_config, state_info["current_state"], storage_path)
    result = _response_envelope(
        state_info=state_info,
        storage_path=storage_path,
        agent=agent,
        instructions=instructions,
        menu=menu,
        preferred_adapter=_resolve_adapter(flow_config, state_info["current_state"]),
    )
    result["limits"] = state_info["limits"]
    return result


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
                append_event(
                    storage_path, {"type": "FEEDBACK_RESOLVED", "file": filename}
                )

    state_file = storage_path / "STATE.json"
    state_before: dict | None = None
    if state_file.exists():
        try:
            state_before = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state_before = None

    try:
        state_info = recover_state(storage_path, flow_config)
    except Exception as e:
        return {
            "schema_version": _SCHEMA_VERSION,
            "decision": "escalate",
            "current_state": "UNKNOWN",
            "conv": 0,
            "role": "human",
            "agent": "human",
            "agent_hint": {"agent": "human", "role": "human", "mode": "escalate", "instructions": "FSM state is corrupt or unreadable. Human intervention required."},
            "stage_brief": {"state": "UNKNOWN", "conv": 0, "retry_count": 0, "open_feedback": [], "feedback_age_hours": None, "recent_events": [], "recent_consult": None, "plan_path": ""},
            "warnings": [{"code": "corrupt_state", "message": str(e)}],
            "blocked": True,
            "target_agent": "human",
            "file": "HUMAN_QUESTIONS.md",
            "instructions": f"FSM state recovery failed: {e}",
            "storage_path": str(storage_path),
        }

    feedback = route_feedback(flow_config, storage_path)
    if feedback is not None:
        result = _blocked_response(feedback, state_info, storage_path,
                                   preferred_adapter=_resolve_adapter(flow_config, state_info["current_state"]))
        if feedback["target_agent"] != "human":
            try:
                instructions = build_prompt_for_agent(
                    flow_config, feedback["target_agent"], storage_path
                )
                result["instructions"] = instructions
                result["agent_hint"] = _agent_hint(feedback["target_agent"], instructions)
                result["codex_subagent"] = _codex_subagent_hint(feedback["target_agent"], instructions)
            except Exception:
                result["instructions"] = None
        return result

    if state_info["current_state"] == "DONE":
        return {"done": True}

    eval_result: str | dict = evaluate_transition_rules(
        flow_config, state_info["current_state"], storage_path
    )

    if isinstance(eval_result, dict) and eval_result.get("decide") is True:
        if decision is None:
            context_file = eval_result.get("context_file", "")
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
                "question": eval_result["question"],
                "context": context_contents,
                "options": eval_result["options"],
                "default": eval_result["default"],
            }
        else:
            options = eval_result["options"]
            default = eval_result["default"]
            if decision not in options:
                decision = default
            next_state = options.get(decision, options.get(default, ""))
            append_event(
                storage_path,
                {
                    "type": "DECIDE_ROUTING",
                    "chosen": next_state,
                    "decision_input": decision,
                    "options": options,
                },
            )
    else:
        if not isinstance(eval_result, str):
            raise RuntimeError(
                f"evaluate_transition_rules returned unexpected type {type(eval_result)!r}; "
                f"expected str or decide-dict"
            )
        next_state = eval_result

    gate_failure = run_gates(
        flow_config, state_info["current_state"], next_state,
        storage_path, topic, state_info["conv"]
    )
    if gate_failure is not None:
        feedback = route_feedback(flow_config, storage_path)
        if feedback is None:
            feedback = {"target_agent": "human", "file": gate_failure.get("feedback_file", "HUMAN_QUESTIONS.md")}
        result = _blocked_response(feedback, state_info, storage_path,
                                   preferred_adapter=_resolve_adapter(flow_config, state_info["current_state"]))
        if feedback["target_agent"] != "human":
            try:
                instructions = build_prompt_for_agent(
                    flow_config, feedback["target_agent"], storage_path
                )
                result["instructions"] = instructions
                result["agent_hint"] = _agent_hint(feedback["target_agent"], instructions)
                result["codex_subagent"] = _codex_subagent_hint(
                    feedback["target_agent"], instructions
                )
            except Exception:
                result["instructions"] = None
        return result

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

    prior_state = dict(state_before or {})
    # Clear per-conversation baselines so the next conversation gets fresh snapshots.
    prior_state.pop("conv_start_sha", None)
    prior_state.pop("build_baseline", None)
    write_state(storage_path, next_state, prior_state)

    append_event(
        storage_path,
        {
            "type": "STATE_TRANSITION",
            "from": state_info["current_state"],
            "to": next_state,
        },
        flow=flow_config,
    )

    if next_state == "DONE":
        return {"done": True}

    instructions = build_prompt(flow_config, next_state, storage_path)
    agent = flow_config["agent_map"][next_state]
    menu = build_menu_payload(flow_config, next_state, storage_path)
    result = _response_envelope(
        state_info=state_info,
        storage_path=storage_path,
        agent=agent,
        instructions=instructions,
        menu=menu,
        current_state_value=next_state,
        preferred_adapter=_resolve_adapter(flow_config, next_state),
    )
    result["limits"] = state_info["limits"]
    return result
