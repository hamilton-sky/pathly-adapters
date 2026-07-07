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
    skill: str | None = None,
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
        if skill is not None:
            from pathly_orchestrator.compose import manifest_role_file
            entry = manifest_role_file(agent_role, skill)
            if entry is not None:
                out_path = f"{feature_path}/{entry[0]}"
                text = text.replace("<out_path>", out_path)
    return text


def _changed_files(project_root: str, limit: int = 3) -> list[str]:
    """Return up to ``limit`` code files changed in the working tree — the task's
    file scope for the code-structure channel — or ``[]`` on any failure.

    Bounded and never raises: a git failure or non-repo just yields no scope, so
    the channel is simply absent (the "never break the prompt" idiom).
    """
    try:
        import subprocess

        out = subprocess.run(
            ["git", "-C", project_root, "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return []
        exts = (".py", ".ts", ".tsx", ".js", ".jsx")
        files = [
            ln.strip() for ln in out.stdout.splitlines() if ln.strip().endswith(exts)
        ]
        return files[:limit]
    except Exception:
        return []


def _project_root_from_storage(storage_path: Path) -> str:
    """Project root = everything above the ``pathly/`` storage anchor.

    Robust to nesting depth — flat ``pathly/<topic>``, Phase-1 ``pathly/features/<f>/plans``,
    or Phase-2 ``pathly/features/<f>/goals/<slug>`` all yield the same root. The old
    ``storage_path.parent.parent.parent`` assumed the flat 3-level layout and misderived
    the root for any nested path (a latent bug the moment ``features/<name>/plans`` shipped).
    Uses the LAST ``pathly`` path segment so a project dir like ``…/pathly-adapters`` (whose
    own name is not exactly ``pathly``) is never mistaken for the anchor.
    """
    parts = storage_path.parts
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "pathly":
            return str(Path(*parts[:i])) if i > 0 else str(storage_path.anchor or ".")
    # No 'pathly' anchor (unexpected) — fall back to the legacy flat-layout assumption.
    return str(storage_path.parent.parent.parent)


def build_prompt(
    flow_config: dict,
    state_name: str,
    storage_path: Path,
    goal_id: str = "",
) -> str:
    agent = flow_config["agent_map"][state_name]
    feature = storage_path.name
    project_root = _project_root_from_storage(storage_path)
    # Board scope the stage posts to / retrieves context from. A plain feature
    # pipeline: this IS the feature (the storage dir name). A goal-decompose run
    # (the consultation FSM): the on-disk topic is the goal slug for run isolation,
    # but board writes must target the parent feature/project board the goal lives
    # on — else the PO/architect/… artifacts orphan onto a throwaway slug-scoped
    # board instead of the board the consultation was spawned from (the bug fix).
    board_scope = feature
    if goal_id:
        try:
            from pathly_orchestrator.db.connection import get_db as _gd
            from pathly_orchestrator.db.queries.comms_messages import (
                get_goal_board_scope as _ggbs,
            )

            _bs = _ggbs(_gd(project_root or None), goal_id)
            if _bs is not None:
                # _bs = (board_tier, scope). We take only the scope: the board-post
                # fragments (comms-post, board-init) and record-phase hardcode
                # board='feature', so the *feature*-tier goal path is what's fully
                # supported here. A project/global-tier goal decompose is an edge case
                # (project goals normally become features, not DAG-decomposed): its
                # posts would land under scope=<project_root> on the feature board, and
                # its project-board context is still surfaced via retrieve_board_context's
                # own project channel. Threading _bs[0] through to the post sites is a
                # follow-up (needs a `<board>` fragment variable), not done here.
                board_scope = _bs[1]
        except Exception:
            board_scope = feature
    _role = _SKILL_AGENT_ROLE.get(agent)
    agent_role: str = (
        _role
        if _role is not None
        else (agent.split("/")[-1] if "/" in agent else agent)
    )

    if "/" in agent:
        from pathly_orchestrator.compose import (
            build_adapter_caps,
            compose_skill,
            compose_skill_with_block,
            load_effective_manifest,
        )

        adapter = _resolve_adapter(flow_config, state_name) or "claude"
        # Thread goal_id into the caps so goal_id-gated fragments (task-dag-post,
        # board-start-context) survive composition on the FSM/consultation path —
        # mirroring the start_board_run decompose path. Without this the terminal
        # planner stage loses its DAG-seeding fragment and no task DAG ever lands
        # on the board (the whole point of a goal decompose/executor run).
        caps = build_adapter_caps(adapter, goal_id=goal_id or "")
        manifest = load_effective_manifest(project_root)
        composition = flow_config.get("composition", {})
        block_name = composition.get(state_name)
        if block_name:
            try:
                agent_text = compose_skill_with_block(
                    agent, block_name, caps, manifest=manifest
                )
            except KeyError:
                logging.getLogger(__name__).warning(
                    "composition-blocks: unknown block %r for state %r — falling back to compose_skill",
                    block_name,
                    state_name,
                )
                agent_text = compose_skill(agent, caps, manifest=manifest)
        else:
            agent_text = compose_skill(agent, caps, manifest=manifest)
    else:
        agent_text = _load_agent_text(agent)

    agent_text = _inject_prompt_vars(
        agent_text, board_scope, project_root, agent_role, storage_path=storage_path,
        skill=(agent if "/" in agent else None),
    )

    context = (
        f"\n\n## Current task\n"
        f"Feature: {board_scope}\n"
        f"State: {state_name}\n"
        f"Storage path: {storage_path}\n"
        "\n"
        "### Runner contract — the supervisor owns the FSM\n"
        "You are running headless under the Pathly supervisor, which drives every state "
        "transition. Do your stage's work, write your artifact(s), post progress and results "
        "to the board (`/comms/*`), then STOP. Do NOT advance the pipeline yourself: never run "
        "`pathly-fsm-call`, never call `complete-stage`/`next-action`, never POST to "
        "`/complete_stage` or `/next_action`, and do NOT route back to another skill (e.g. "
        "`team <feature> …`). The supervisor advances the flow automatically once your artifact "
        "exists — any transition you trigger yourself causes a double-advance or a 404 loop. "
        "(Any `FSM operations` / `complete-stage` / `route back` instructions in the skill above "
        "apply ONLY to interactive `/pathly` use and must be ignored here.)\n"
    )
    from pathly_orchestrator.runner import build_pipeline_history_block

    # Pipeline history is the RUN's own inter-stage progress, keyed by the run identity
    # (this run's storage dir), NOT the board scope. A multi-stage consultation must see its
    # OWN earlier stages (PO → architect → …), not the parent feature's unrelated pipeline
    # history — so this read uses storage_path itself (the already-resolved run dir), while
    # board writes/context/telemetry above use `board_scope`. (Previously rebuilt a flat
    # pathly/plans/<feature> path, which both used the legacy base AND flattened a nested
    # goal/consultation storage dir it was already handed correctly.)
    feature_dir = str(storage_path)
    history = build_pipeline_history_block(feature_dir)

    board_block = ""
    try:
        from pathly_orchestrator.db.connection import get_db as _get_db_comms
        from pathly_orchestrator.db.queries.app_settings import get_board_scope
        from pathly_orchestrator.runner.comms_context import retrieve_board_context

        _conn = _get_db_comms()
        _scope = get_board_scope(_conn, project_root, board_scope)
        board_block = retrieve_board_context(
            topic=board_scope,
            project_root=project_root,
            task_description=context,
            board_scope=_scope,
        )
    except Exception:
        pass

    # Code structure channel (B-inject). Shares the runner.code_context
    # backend with the C proxy. Gated on a configured backend so the default
    # (off) path stays zero-cost — no git call, no block — exactly as before.
    code_block = ""
    try:
        from pathly_orchestrator.runner.code_context import (
            build_block as _code_build_block,
            maybe_reindex as _code_maybe_reindex,
            _resolve_backend as _code_resolve_backend,
        )

        if _code_resolve_backend() != "none":
            # Freshness bridge: async, non-blocking; refreshes the graph for the
            # next stage per the code_context.reindex setting (no-op unless stage).
            _code_maybe_reindex(project_root)
            _code_files = _changed_files(project_root)
            if _code_files:
                code_block = _code_build_block(
                    board_scope, _code_files, agent_role, 1200, project_root
                )
    except Exception:
        pass

    prompt = agent_text + context + history
    if board_block:
        prompt += "\n" + board_block
    if code_block:
        prompt += "\n" + code_block
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
