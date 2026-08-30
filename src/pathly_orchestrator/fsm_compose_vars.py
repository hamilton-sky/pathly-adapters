"""Filling a stage prompt's placeholders.

``_inject_prompt_vars`` is the substitution pass every FSM-composed prompt goes through; the
two helpers below supply the values it cannot read off the state (recent changed files, the
project root implied by a storage path).
"""

from __future__ import annotations

import re
from pathlib import Path


def _inject_prompt_vars(
    text: str,
    feature: str,
    project_root: str,
    agent_role: str,
    storage_path: Path | None = None,
    skill: str | None = None,
    board_tier: str = "feature",
    run_category: str = "flow",
    board_scope_cfg: dict[str, bool] | None = None,
) -> str:
    """Replace log-phase markers and common placeholders with real values.

    ``run_category`` is the run TYPE (``flow``|``single``|``loop``) written into the
    completion-report ``AGENT_DONE`` so the Monitor's RECENT list buckets a finished run the
    same way its live card did. FSM/team stages are ``flow`` (this default); board/single runs
    override it to ``single`` via ``board_run._inject_board_prompt_vars``.

    ``board_scope_cfg`` is the run's already-resolved tier selection, used for the
    ``<search_tiers>`` the board-search fragment hands the agent. Omitted, it is looked up from
    ``board_tier``/``feature``/``agent_role`` — which is what lets the board-run path (which
    reuses this function) substitute the placeholder without wiring a second resolution of its
    own, and keeps it resolving from the SAME setting as the context pushed into that prompt.
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
    # <search_tiers> = the board tiers this run may query ITSELF via /comms/search, with the
    # scope addressing each — the board-search fragment's whole reach. Guarded on presence
    # because resolving the tiers can hit the DB, and only the handful of skills that compose
    # that fragment carry the placeholder; every other prompt must stay free.
    if "<search_tiers>" in text:
        from pathly_orchestrator.runner.board_scope import (
            resolve_board_scope_setting,
            search_tiers_value,
        )

        tiers = (
            board_scope_cfg
            if board_scope_cfg is not None
            else resolve_board_scope_setting(
                board_tier, feature, project_root, agent_role
            )
        )
        text = text.replace(
            "<search_tiers>", search_tiers_value(tiers, feature, project_root)
        )
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
