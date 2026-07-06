"""FSM transition actions, gate evaluation, and state/event persistence."""

from __future__ import annotations

import json
import re
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
) -> None:
    """Execute transition_actions for prev_state->next_state (and ->next_state wildcard)."""
    transition_actions = flow.get("transition_actions") or {}

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
                    "git", "add", "--", str(storage_path), *[str(p) for p in _paths]
                ]
            else:
                add_cmd = ["git", "add", "-A"]
            try:
                try:
                    add_result = subprocess.run(
                        add_cmd, cwd=str(project_root), capture_output=True,
                        text=True, timeout=30,
                    )
                except subprocess.TimeoutExpired:
                    raise RuntimeError("git add timed out after 30 seconds")
                if add_result.returncode != 0:
                    raise RuntimeError(f"git add failed: {add_result.stderr}")
                try:
                    commit_result = subprocess.run(
                        ["git", "commit", "-m", message], cwd=str(project_root),
                        capture_output=True, text=True, timeout=30,
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

        elif skill == "update_progress":
            progress_file = storage_path / "PROGRESS.md"
            if not progress_file.exists():
                continue
            mark = action.get("mark", "")
            try:
                content = progress_file.read_text(encoding="utf-8")
                if mark == "conv_done":
                    content = content.replace(f"| {conv} |", f"| {conv} | DONE |", 1)
                    try:
                        from pathly_orchestrator import eventlog as _eventlog
                        from pathly_orchestrator.eventlog import VALID_STATES

                        state_doc = _eventlog.read_state(str(storage_path)) or {}
                        state_doc["convs_done"] = (
                            int(state_doc.get("convs_done", 0)) + 1
                        )
                        if state_doc.get("current") not in VALID_STATES:
                            state_doc["current"] = prev_state
                        _eventlog.write_state(str(storage_path), state_doc)
                    except (ValueError, OSError):
                        pass
                elif mark == "all_phases_done":
                    content = re.sub(r"\|\s*\[ \]\s*\|", "| [x] |", content)
                progress_file.write_text(content, encoding="utf-8")
            except OSError as e:
                raise RuntimeError(f"update_progress failed: {e}")

        else:
            raise RuntimeError(f"Unknown action skill: {skill!r}")


def _verify_passed(path: Path, marker: str) -> bool:
    if not path.exists():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    lines = text.splitlines()
    return bool(lines) and lines[0].strip() == marker


def _write_gate_feedback(storage_path: Path, on_fail: str, reason: str) -> None:
    feedback_dir = storage_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    target = feedback_dir / on_fail
    target.write_text(reason, encoding="utf-8")


def _scope_clean(
    storage_path: Path,
    scope_file: str,
    preexisting_dirty: set[str] | None,
    flow: dict | None = None,
) -> bool:
    import re as _re

    scope_path = storage_path / scope_file
    declared: set[str] = set()

    if scope_path.exists():
        try:
            text = scope_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        for line in text.splitlines():
            for match in _re.finditer(r"`([^`\r\n]+)`", line):
                candidate = match.group(1).strip()
                if candidate:
                    declared.add(candidate)

    if not declared:
        append_event(
            storage_path,
            {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "no_declared_scope"},
        )
        return True

    project_root = storage_path.parent.parent.parent

    try:
        diff_result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=str(project_root), capture_output=True, text=True, timeout=30,
        )
    except Exception:
        append_event(
            storage_path,
            {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "git_diff_failed"},
        )
        return True

    if diff_result.returncode != 0:
        append_event(
            storage_path,
            {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "git_diff_failed"},
        )
        return True

    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=str(project_root), capture_output=True, text=True, timeout=30,
        )
        untracked = (
            {
                line[3:].strip()
                for line in status_result.stdout.splitlines()
                if line.startswith("??")
            }
            if status_result.returncode == 0
            else set()
        )
    except Exception:
        untracked = set()

    all_dirty = {p for p in diff_result.stdout.splitlines() if p.strip()} | untracked
    builder_touched = all_dirty - (preexisting_dirty or set())

    extra_prefixes: list[str] = []
    if flow:
        extra_prefixes = flow.get("scope_gate", {}).get("exempt_prefixes", []) or []

    def _is_exempt(p: str) -> bool:
        # A feature's own storage tree is exempt from the builder scope gate: the flat home
        # (pathly/features/<name>/) and the legacy base (pathly/plans/<name>/) both count.
        if (
            p.startswith("pathly/features/")
            or p.startswith("pathly/plans/")
            or p.endswith(".tsbuildinfo")
        ):
            return True
        return any(p.startswith(prefix) for prefix in extra_prefixes)

    for path in builder_touched:
        if not _is_exempt(path) and path not in declared:
            return False

    return True


def run_gates(
    flow: dict,
    prev_state: str,
    next_state: str,
    storage_path: Path,
    topic: str,
    conv: int,
    goal_id: str | None = None,
) -> dict | None:
    gates = flow.get("gates", {})
    applicable = gates.get(f"{prev_state}->{next_state}", []) + gates.get(
        f"->{next_state}", []
    )

    for gate in applicable:
        gtype = gate["type"]
        if gtype == "require_artifact":
            artifact_path = storage_path / gate["artifact"]
            if not artifact_path.exists():
                reason = f"Required artifact missing: {gate['artifact']}"
                _write_gate_feedback(storage_path, gate["on_fail"], reason)
                append_event(
                    storage_path,
                    {"type": "GATE_FAILED", "gate": gtype, "transition": f"{prev_state}->{next_state}"},
                )
                return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        elif gtype == "verify_gate":
            artifact_path = storage_path / gate["artifact"]
            marker = gate["pass_marker"]
            if not _verify_passed(artifact_path, marker):
                reason = (
                    f"VERIFY gate failed: `{gate['artifact']}` is missing or its first line "
                    f"is not exactly {marker!r}.\n\n"
                    f"**Action required:** Write `{storage_path / gate['artifact']}` "
                    f"so that line 1 is exactly:\n\n"
                    f"```\n{marker}\n```\n\n"
                    f"No YAML frontmatter, no blank lines before it."
                )
                _write_gate_feedback(storage_path, gate["on_fail"], reason)
                append_event(
                    storage_path,
                    {"type": "GATE_FAILED", "gate": gtype, "transition": f"{prev_state}->{next_state}"},
                )
                return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        elif gtype == "require_tasks_done":
            # Goal-DAG completeness: a goal must not finish (reach RETRO) while any of its tasks
            # are unfinished or failed. Skipped for non-goal runs (goal_id is None) — a plain
            # feature pipeline has no task DAG to check.
            if goal_id:
                try:
                    from pathly_orchestrator.db.connection import get_db
                    from pathly_orchestrator.db.queries.comms_tasks import (
                        count_incomplete_tasks_for_goal,
                    )

                    incomplete = count_incomplete_tasks_for_goal(get_db(), goal_id)
                except Exception:
                    incomplete = 0  # DB read error → fail-open (never wedge on a read hiccup)
                if incomplete > 0:
                    reason = (
                        f"{incomplete} task(s) on this goal are not done — a goal cannot finish "
                        f"while tasks remain unfinished or failed. Build/repair the remaining "
                        f"tasks (they are on the board's DAG), then the flow can advance to retro."
                    )
                    _write_gate_feedback(storage_path, gate["on_fail"], reason)
                    append_event(
                        storage_path,
                        {"type": "GATE_FAILED", "gate": gtype, "transition": f"{prev_state}->{next_state}"},
                    )
                    return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        elif gtype == "scope_gate":
            scope_file = gate["scope_file"]
            build_baseline: dict | None = None
            try:
                from pathly_orchestrator.eventlog import read_state as _read_state_db

                _state_doc = _read_state_db(str(storage_path))
                if _state_doc:
                    build_baseline = _state_doc.get("build_baseline")
            except Exception:
                build_baseline = None
            if build_baseline is None:
                state_file = storage_path / "STATE.json"
                if state_file.exists():
                    try:
                        state_doc = json.loads(state_file.read_text(encoding="utf-8"))
                        build_baseline = state_doc.get("build_baseline")
                    except (json.JSONDecodeError, OSError):
                        pass
            if build_baseline is None:
                append_event(
                    storage_path,
                    {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "no_build_baseline"},
                )
                continue
            if (
                build_baseline.get("truncated")
                or len(build_baseline.get("preexisting_dirty", [])) > 500
            ):
                append_event(
                    storage_path,
                    {"type": "GATE_DEGRADED", "gate": "scope_gate", "reason": "preexisting_dirty_truncated"},
                )
                continue
            preexisting = set(build_baseline.get("preexisting_dirty", []))
            if not _scope_clean(storage_path, scope_file, preexisting, flow=flow):
                reason = f"Scope gate failed: changes outside declared scope in {scope_file}"
                _write_gate_feedback(storage_path, gate["on_fail"], reason)
                append_event(
                    storage_path,
                    {"type": "GATE_FAILED", "gate": gtype, "transition": f"{prev_state}->{next_state}"},
                )
                return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        else:
            raise RuntimeError(f"Unknown gate type: {gtype!r}")
    return None


def write_state(storage_path: Path, next_state: str, prior_state: dict) -> None:
    """Write STATE.json atomically (write to .tmp then rename)."""
    storage_path.mkdir(parents=True, exist_ok=True)
    new_state = dict(prior_state)
    new_state["current"] = next_state

    state_file = storage_path / "STATE.json"
    tmp_file = storage_path / "STATE.json.tmp"

    tmp_file.write_text(json.dumps(new_state, indent=2) + "\n", encoding="utf-8")
    tmp_file.replace(state_file)


def append_event(storage_path: Path, event: dict, flow: dict | None = None) -> None:
    from pathly_orchestrator.eventlog import append_event as _append_event

    _append_event(str(storage_path), event, flow=flow)
