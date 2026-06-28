"""FSM prompt composition and hint building — transport-independent."""

from __future__ import annotations

import logging
import re
from pathlib import Path

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

_SKILL_AGENT_ROLE: dict[str, str] = {
    "team/build": "builder",
    "team/review": "reviewer",
    "team/test": "tester",
    "team/plan": "planner",
    "team/design": "designer",
    "team/retro": "planner",
}


def _load_agent_text(agent: str) -> str:
    from importlib.resources import files

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
    return files("pathly_data").joinpath(relative_path).read_text(encoding="utf-8")


def _inject_prompt_vars(
    text: str,
    feature: str,
    project_root: str,
    agent_role: str,
    storage_path: Path | None = None,
) -> str:
    """Replace log-phase markers and common placeholders with real values."""

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
    agent_role: str = (
        _role
        if _role is not None
        else (agent.split("/")[-1] if "/" in agent else agent)
    )

    if "/" in agent:
        from pathly_orchestrator.compose import (
            compose_skill,
            compose_skill_with_block,
            load_effective_manifest,
        )

        adapter = _resolve_adapter(flow_config, state_name) or "claude"
        manifest = load_effective_manifest(project_root)
        composition = flow_config.get("composition", {})
        block_name = composition.get(state_name)
        if block_name:
            try:
                agent_text = compose_skill_with_block(
                    agent, block_name, adapter, manifest=manifest
                )
            except KeyError:
                logging.getLogger(__name__).warning(
                    "composition-blocks: unknown block %r for state %r — falling back to compose_skill",
                    block_name,
                    state_name,
                )
                agent_text = compose_skill(agent, adapter, manifest=manifest)
        else:
            agent_text = compose_skill(agent, adapter, manifest=manifest)
    else:
        agent_text = _load_agent_text(agent)

    agent_text = _inject_prompt_vars(
        agent_text, feature, project_root, agent_role, storage_path=storage_path
    )

    context = (
        f"\n\n## Current task\n"
        f"Feature: {feature}\n"
        f"State: {state_name}\n"
        f"Storage path: {storage_path}\n"
    )
    from pathly_orchestrator.runner import build_pipeline_history_block
    import os

    feature_dir = os.path.join(project_root, "pathly", "plans", feature)
    history = build_pipeline_history_block(feature_dir)

    board_block = ""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db_comms
        from pathly_orchestrator.db.queries.app_settings import get_board_scope
        from pathly_orchestrator.runner.comms_context import retrieve_board_context

        _conn = _get_db_comms()
        _scope = get_board_scope(_conn, project_root, feature)
        board_block = retrieve_board_context(
            topic=feature,
            project_root=project_root,
            task_description=context,
            board_scope=_scope,
        )
    except Exception:
        pass

    prompt = agent_text + context + history
    if board_block:
        prompt += "\n" + board_block
    return prompt


def build_prompt_for_agent(
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


def _resolve_adapter(flow_config: dict, state_name: str) -> str:
    adapter_map = flow_config.get("adapter_map") or {}
    return adapter_map.get(state_name) or adapter_map.get("default") or ""


# Re-export response/menu builders from fsm_compose_responses.
# Bottom-of-file: all names above (_agent_hint, _SCHEMA_VERSION, etc.) are
# already defined when Python triggers loading fsm_compose_responses, so
# its top-level imports from this module succeed without a cycle.
from pathly_orchestrator.fsm_compose_responses import (  # noqa: E402, F401
    _blocked_response,
    _exit_requirement,
    _response_envelope,
    _stage_brief,
    build_menu_payload,
)
