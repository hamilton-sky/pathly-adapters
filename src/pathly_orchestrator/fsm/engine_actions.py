"""FSM transition actions (commit, archive-artifacts, …).

Gate evaluation used to live here too; it now has its own package (``fsm.gates``, one
module per gate type) so a new gate is a NEW FILE rather than another ``elif`` in this
one. The gate names below are re-exported for backward compatibility only — new code
should import them from ``pathly_orchestrator.fsm.gates``.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def _auto_commit_enabled(action: dict) -> bool:
    """Resolve whether the commit transition-action may run.

    Precedence: explicit action["auto_commit"] > app-setting pathly.auto_commit > False.
    Default OFF — an unattended FSM advance never commits without explicit opt-in.
    """
    if "auto_commit" in action:
        return bool(action["auto_commit"])
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), "pathly.auto_commit", "false")
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
    except Exception:
        return False


def _post_commit_skipped_note(
    topic: str, prev_state: str, next_state: str, project_root: Path
) -> None:
    """Advisory board note when auto-commit is gated off. Best-effort; never raises."""
    n = -1
    try:
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=15,
        )
        n = len([ln for ln in status.stdout.splitlines() if ln.strip()])
    except Exception:
        pass
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.comms import post_message

        count = f"{n} changed file(s)" if n >= 0 else "pending changes"
        post_message(
            get_db(),
            board="feature",
            scope=topic,
            from_agent="orchestrator",
            type="decision",
            text=(
                f"Stage {prev_state} → {next_state} complete — {count} ready to commit. "
                "Auto-commit is OFF (pathly.auto_commit); commit when you've reviewed."
            ),
            stage=next_state,
        )
    except Exception:
        pass


def run_transition_actions(
    flow: dict,
    prev_state: str,
    next_state: str,
    storage_path: Path,
    topic: str,
    conv: int,
    project_root: Path | str | None = None,
) -> None:
    """Execute transition_actions for prev_state->next_state (and ->next_state wildcard).

    project_root: the repo root — the base for archive-artifacts' pipeline-walkthrough dir and the
    auto-commit cwd. Pass it explicitly; callers know it. When omitted we FALL BACK to deriving it
    by walking ``storage_path`` up by the number of segments in the flow's ``storage_path`` template.
    That derivation is WRONG when ``{topic}`` expands to a multi-segment board-scoped path (e.g.
    ``features/<f>/goals/<slug>``): it undershoots and lands on the feature dir instead of the repo
    root, which nests ``pathly/pipeline-walkthrough/...`` INSIDE the feature folder.
    """
    transition_actions = flow.get("transition_actions") or {}

    if project_root is not None:
        project_root = Path(project_root)
    else:
        storage_template = flow.get("storage_path", "")
        depth = len([p for p in storage_template.rstrip("/").split("/") if p])
        project_root = storage_path
        for _ in range(depth):
            project_root = project_root.parent

    exact_key = f"{prev_state}->{next_state}"
    wildcard_key = f"->{next_state}"

    actions_to_run: list[dict] = []
    if exact_key in transition_actions:
        actions = transition_actions[exact_key]
        if actions:
            actions_to_run.extend(actions)
    if wildcard_key in transition_actions:
        actions = transition_actions[wildcard_key]
        if actions:
            actions_to_run.extend(actions)

    for action in actions_to_run:
        skill = action.get("skill", "")

        if skill in ("commit", "git_commit"):
            if not _auto_commit_enabled(action):
                _post_commit_skipped_note(topic, prev_state, next_state, project_root)
                continue
            message = action.get(
                "message", f"chore: transition {prev_state}->{next_state}"
            )
            _paths = action.get("paths")
            if isinstance(_paths, list) and _paths:
                add_cmd = [
                    "git",
                    "add",
                    "--",
                    str(storage_path),
                    *[str(p) for p in _paths],
                ]
            else:
                add_cmd = ["git", "add", "-A"]
            try:
                try:
                    add_result = subprocess.run(
                        add_cmd,
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except subprocess.TimeoutExpired:
                    raise RuntimeError("git add timed out after 30 seconds")
                if add_result.returncode != 0:
                    raise RuntimeError(f"git add failed: {add_result.stderr}")
                try:
                    commit_result = subprocess.run(
                        ["git", "commit", "-m", message],
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                except subprocess.TimeoutExpired:
                    raise RuntimeError("git commit timed out after 30 seconds")
                if commit_result.returncode != 0:
                    output = commit_result.stdout + commit_result.stderr
                    if (
                        "nothing to commit" in output
                        or "nothing added to commit" in output
                    ):
                        pass
                    else:
                        raise RuntimeError(f"git commit failed: {output}")
            except FileNotFoundError:
                raise RuntimeError("git executable not found")

        elif skill in ("archive-artifacts", "archive_artifacts"):
            feedback_dir = storage_path / "feedback"
            if not feedback_dir.exists():
                continue
            artifacts_dir = (
                project_root / "pathly" / "pipeline-walkthrough" / topic / "artifacts"
            )
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            for md_file in sorted(feedback_dir.glob("*.md")):
                name = md_file.stem
                pattern = f"{name}_conv{conv}_attempt*.md"
                existing = list(artifacts_dir.glob(pattern))
                attempt = len(existing) + 1
                dest = artifacts_dir / f"{name}_conv{conv}_attempt{attempt}.md"
                try:
                    shutil.copy2(md_file, dest)
                except OSError as e:
                    raise RuntimeError(
                        f"archive-artifacts failed copying {md_file.name}: {e}"
                    )

        else:
            raise RuntimeError(f"Unknown action skill: {skill!r}")


# ── Backward-compatible re-exports ────────────────────────────────────────────
# `fsm/__init__.py`, `fsm/engine.py`, `fsm_ops*.py` and existing tests import these from
# here. The implementations live in `fsm.gates`.
from .gates import (  # noqa: E402,F401
    _scope_clean,
    _verify_passed,
    _write_gate_feedback,
    append_event,
    run_gates,
)
