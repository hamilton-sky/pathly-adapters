"""FSM prompt composition and hint building — transport-independent."""

from __future__ import annotations

import logging
from pathlib import Path

from .fsm_compose_tables import (
    _AGENT_GROUPS,
    _CODEX_EXPLORER_AGENTS,
    _MENU_LABELS,
    _STATE_TO_COMMAND,
    _SCHEMA_VERSION,
    _SKILL_AGENT_ROLE,
    _FIX_MODE_ARTIFACT,
)
from .fsm_compose_vars import (
    _inject_prompt_vars,
    _changed_files,
    _project_root_from_storage,
)
from .fsm_compose_paths import resolve_stage_out_path, resolve_board_scope
from .fsm_compose_stage import _drop_sections, _apply_stage_selection, _resolve_adapter
from .fsm_compose_hints import _codex_subagent_hint, _agent_hint

__all__ = [
    "build_prompt",
    "build_prompt_for_agent",
    "_load_agent_text",
    "_inject_prompt_vars",
    "_changed_files",
    "_project_root_from_storage",
    "resolve_stage_out_path",
    "resolve_board_scope",
    "_drop_sections",
    "_apply_stage_selection",
    "_resolve_adapter",
    "_codex_subagent_hint",
    "_agent_hint",
    "_AGENT_GROUPS",
    "_MENU_LABELS",
    "_STATE_TO_COMMAND",
    "_SCHEMA_VERSION",
    "_SKILL_AGENT_ROLE",
    "_FIX_MODE_ARTIFACT",
    "_CODEX_EXPLORER_AGENTS",
    "_blocked_response",
    "_exit_requirement",
    "_response_envelope",
    "_stage_brief",
    "build_menu_payload",
]


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


def build_prompt(
    flow_config: dict,
    state_name: str,
    storage_path: Path,
    goal_id: str = "",
    ability_ids: list | None = None,
    excluded_sections: list | None = None,
    stage_override: str = "",
) -> str:
    agent = flow_config["agent_map"][state_name]
    feature = storage_path.name
    project_root = _project_root_from_storage(storage_path)
    board_scope = resolve_board_scope(feature, project_root, goal_id)
    # Board tier for the <board> prompt var → the comms-post fragment posts artifacts to the
    # RIGHT channel. Only a project run (storage basename 'project') targets the project board;
    # every other run stays 'feature' — also the value /comms/post coerces any unknown board to,
    # so an unsubstituted <board> can never mis-post.
    board_tier = "project" if feature == "project" else "feature"
    _role = _SKILL_AGENT_ROLE.get(agent)
    agent_role: str = (
        _role
        if _role is not None
        else (agent.split("/")[-1] if "/" in agent else agent)
    )

    # ONE predicate for "an override is in effect", used both to swap the body (below) and to
    # skip the persistent stage-selection (R4). A whitespace-only override counts as absent for
    # BOTH — so it composes normally AND still applies the stage's saved selection (no silent drop).
    _has_override = bool(stage_override and stage_override.strip())
    if _has_override:
        # Flow-gate-preview (P2): a transient, per-run, per-stage prompt trim/edit from the
        # gate — verbatim in place of the composed body ONLY (mirrors board_run's
        # prompt_override). Skips compose entirely AND _apply_stage_selection below (never
        # double-trim — the human already saw/edited the final text at the gate; DESIGN.md
        # R4). The runner-contract/history/board/code tail further down still applies,
        # exactly like a composed stage.
        agent_text = stage_override
    elif "/" in agent:
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
        # board_default=True: if a flow's agent_map points at a custom skill (absent from the
        # manifest), give it the default board bundle rather than a raw body — the same
        # "compose through fragments" guarantee the /comms/run board path provides. Recognized
        # skills (team/build, …) are listed in the manifest, so this flag never affects them.
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
                agent_text = compose_skill(
                    agent, caps, manifest=manifest, board_default=True
                )
        else:
            agent_text = compose_skill(
                agent, caps, manifest=manifest, board_default=True
            )
    else:
        agent_text = _load_agent_text(agent)

    # flow-phase-inspector (#5): apply this stage's SAVED selection (layer-3 abilities +
    # excluded sections) to the freshly-composed body. Guarded — a stage with no selection
    # is byte-identical. A single post-compose transform on agent_text, so the delicate
    # compose branches above stay untouched; composing fresh here (never storing trimmed
    # text) is what keeps an upstream skill edit from stale-seeding the run. Skipped when
    # stage_override is set (R4) — the override already IS the final text; re-applying the
    # persistent selection on top of it would double-trim.
    if not _has_override and (ability_ids or excluded_sections):
        agent_text = _apply_stage_selection(
            agent_text, ability_ids, excluded_sections, project_root
        )

    agent_text = _inject_prompt_vars(
        agent_text,
        board_scope,
        project_root,
        agent_role,
        storage_path=storage_path,
        skill=(agent if "/" in agent else None),
        board_tier=board_tier,
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
    feedback_file: str | None = None,
) -> str:
    agent_text = _load_agent_text(agent_name)
    context = (
        f"\n\n## Current task\n"
        f"Feature: {storage_path.name}\n"
        f"Storage path: {storage_path}\n"
    )
    prompt = agent_text + context
    # Fix mode (smart-fix-routing DESIGN.md ss3.1): only appended when the routed target is
    # a root-cause role (po/planner/architect/designer) AND a feedback file was supplied —
    # the builder/reviewer/human path stays byte-identical to before this feature.
    artifact = _FIX_MODE_ARTIFACT.get(agent_name)
    if feedback_file and artifact is not None:
        feature_path = storage_path.as_posix().rstrip("/")
        prompt += (
            f"\n## Fix mode — you are resolving a routed review/test failure\n"
            f"\n"
            f"A reviewer/tester traced a failure to YOUR artifact. You are NOT re-running your\n"
            f"whole stage — you are patching the specific decision that was wrong.\n"
            f"\n"
            f"1. Read  {feature_path}/feedback/{feedback_file}   (the failure + why it is yours).\n"
            f"2. Correct YOUR artifact: {artifact}  (if absent, the nearest equivalent —\n"
            f"   IMPLEMENTATION_PLAN.md / USER_STORIES.md). Change only what the failure requires.\n"
            f"3. Hand off to the builder: if the corrected artifact implies code changes, write\n"
            f"   (or APPEND to) {feature_path}/feedback/REVIEW_FAILURES.md a short [IMPL] section\n"
            f'   naming the change ("implement per updated ARCHITECTURE_PROPOSAL.md §X").\n'
            f"   If the correction is decision-only (no code), skip this — the re-review gate\n"
            f"   will re-verify.\n"
            f"4. Delete {feature_path}/feedback/{feedback_file} when your artifact is corrected.\n"
            f"5. Report what changed. Do NOT run pathly-fsm-call / complete-stage (supervisor owns the FSM).\n"
        )
    return prompt


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
