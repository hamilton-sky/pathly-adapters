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

# Smart fix-routing (fix mode) — role -> the artifact that role corrects when routed a
# feedback file. Only these four are "root-cause" roles: they own a decision artifact
# upstream of the code, so a routed hand-off means "fix your artifact, then hand off to
# the builder" rather than "fix the code" (builder/reviewer/human are excluded — see
# build_prompt_for_agent). Mirrors DESIGN.md ss3.1 (deliberately NOT artifact-manifest.yaml's
# po -> PO_NOTES.md — ss3.1 pins po's fix-mode artifact to USER_STORIES.md, the file the team
# pipeline actually keeps requirements in; reconciling the two is a follow-up, DESIGN.md risk #5).
_FIX_MODE_ARTIFACT: dict[str, str] = {
    "po": "USER_STORIES.md",
    "planner": "IMPLEMENTATION_PLAN.md",
    "architect": "ARCHITECTURE_PROPOSAL.md",
    "designer": "DESIGN.md",
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
    board_tier: str = "feature",
    run_category: str = "flow",
) -> str:
    """Replace log-phase markers and common placeholders with real values.

    ``run_category`` is the run TYPE (``flow``|``single``|``loop``) written into the
    completion-report ``AGENT_DONE`` so the Monitor's RECENT list buckets a finished run the
    same way its live card did. FSM/team stages are ``flow`` (this default); board/single runs
    override it to ``single`` via ``board_run._inject_board_prompt_vars``.
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
    text = text.replace("<run_category>", run_category)
    # <board> = the board TIER (feature|project) this stage writes to — set so the comms-post
    # fragment targets the right channel (a project decompose's artifacts land on the project board).
    text = text.replace("<board>", board_tier)
    text = text.replace("<project_root>", project_root)
    text = text.replace("<agent>", agent_role)
    # <fsm_feature> = the run's FSM/event-log key = the storage dir basename (the run slug).
    # This is what fsm_state, STATE_TRANSITION, every eventlog.append_event(<path>) write, and
    # the DB-explorer goal panel all key by. For a plain feature run it equals <feature>; for a
    # GOAL run <feature> is the parent BOARD scope (so board posts don't orphan onto a throwaway
    # slug board) while <fsm_feature> is the goal slug. Telemetry (AGENT_DONE) MUST key by
    # <fsm_feature> so it lands where the panel + billing reconciliation look — else the goal
    # shows $0 while the cost hides under the feature/board scope.
    fsm_feature = storage_path.name if storage_path is not None else feature
    text = text.replace("<fsm_feature>", fsm_feature)
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


def resolve_stage_out_path(
    flow_config: dict, state_name: str, storage_path: Path
) -> str | None:
    """The on-disk ``<out_path>`` a stage declares (its primary artifact), resolved from the
    composition manifest via the SAME (agent_role, skill) -> ``manifest_role_file`` path
    ``build_prompt`` uses to substitute ``<out_path>`` into the prompt.

    Returns None when the state maps to no composed skill (bare-role stage) or the role has no
    manifest entry. Used by artifact reconciliation to attach a stage's declared output to the
    board directly from the FSM's own record (state-one-authority: replaces the retired
    ARTIFACTS.jsonl ledger scan — no disk mirror)."""
    try:
        agent = (flow_config.get("agent_map") or {}).get(state_name)
        if not agent or "/" not in agent:
            return None
        _role = _SKILL_AGENT_ROLE.get(agent)
        agent_role = _role if _role is not None else agent.split("/")[-1]
        from pathly_orchestrator.compose import manifest_role_file

        entry = manifest_role_file(agent_role, agent)
        if entry is None:
            return None
        feature_path = Path(storage_path).as_posix().rstrip("/")
        return f"{feature_path}/{entry[0]}"
    except Exception:
        return None


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


def _drop_sections(text: str, excluded: set[str]) -> str:
    """Drop ``## <heading>`` blocks whose heading is in ``excluded`` (a flow-inspector
    use-once Sections trim). A block runs from its ``## `` line to the next ``## ``/``# ``
    heading or EOF; ``### `` and body lines inside it go too. Only H2 sections are ever
    trimmable — the gate never lists H1 (the skill title) or locked fragment sections for
    exclusion, so this can never drop platform glue (board CRUD / progress / completion).
    """
    if not excluded:
        return text
    out: list[str] = []
    skip = False
    for line in text.split("\n"):
        is_h2 = line.startswith("## ") and not line.startswith("### ")
        is_h1 = line.startswith("# ") and not line.startswith("## ")
        if is_h2:
            skip = line[3:].strip() in excluded
        elif is_h1:
            skip = False  # a new top-level section ends any skipped H2 block
        if not skip:
            out.append(line)
    return "\n".join(out)


def _apply_stage_selection(
    agent_text: str,
    ability_ids: list | None,
    excluded_sections: list | None,
    project_root: str,
) -> str:
    """Apply a per-stage flow-phase-inspector selection to the freshly-composed stage body
    (#5): drop excluded ``##`` sections, then append the selected layer-3 abilities AFTER the
    body — mirroring ``compose_skill_segments(extra_segments=…)`` on the board-run path. Pure
    and guarded (called only when a selection exists), so a stage with none is byte-identical.
    """
    text = agent_text
    if excluded_sections:
        text = _drop_sections(
            text, {s for s in excluded_sections if isinstance(s, str)}
        )
    if ability_ids:
        try:
            from pathly_orchestrator.skills.abilities import ability_segments

            extras = ability_segments(list(ability_ids), project_root or None)
        except Exception:
            extras = []
        bodies = [s.get("text", "") for s in extras if s.get("text")]
        if bodies:
            text = text.rstrip() + "\n\n" + "\n\n".join(bodies)
    return text


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
    # Board scope the stage posts to / retrieves context from. A plain feature
    # pipeline: this IS the feature (the storage dir name). A goal-decompose run
    # (the consultation FSM): the on-disk topic is the goal slug for run isolation,
    # but board writes must target the parent feature/project board the goal lives
    # on — else the PO/architect/… artifacts orphan onto a throwaway slug-scoped
    # board instead of the board the consultation was spawned from (the bug fix).
    board_scope = feature
    if feature == "project":
        # A PROJECT-scoped run (storage pathly/project/ → basename 'project') posts to / reads
        # the project board, whose scope is the NORMALIZED project_root — NOT the literal
        # 'project' dir basename, which the board + comms_context never key by. Mirrors
        # comms/project.py::_project_scope. Without this the stage's board writes (the
        # project-decompose feature cards, PO/architect notes) orphan at scope='project',
        # invisible on the per-root project board — AND the ≥2-features gate, which counts at
        # scope=project_root, sees 0 and fails the run after it actually seeded features.
        board_scope = (project_root or "").replace("\\", "/").rstrip("/") or feature
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
