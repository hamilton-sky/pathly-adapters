"""
FSM engine for Pathly team-flow pipelines.

Implements state recovery, transition evaluation, feedback routing,
transition actions, and state/event persistence.

Zero LLM SDK imports — only stdlib, yaml, and pathly_orchestrator.state.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import yaml

_DEFAULT_LIMITS = {
    "needs_context_per_stage": 3,
    "feedback_rounds_per_stage": 2,
}


def recover_state(storage_path: Path, flow: dict) -> dict:
    """
    Read STATE.json and EVENTS.jsonl from storage_path.
    Return {"current_state": str, "conv": int, "open_feedback_files": list[str],
            "limits": dict}.
    If STATE.json absent: current_state = first entry in flow["states"].
    open_feedback_files: list of .md filenames in storage_path/feedback/ (stems only, with .md).
    limits: resolved from flow["states"][current_state]["limits"] if present,
            falling back to flow["limits"], falling back to module defaults
            {needs_context_per_stage: 3, feedback_rounds_per_stage: 2}.
    Per-state limits override top-level limits key by key (not wholesale replace).
    conv: read from STATE.json["current_conversation"], default 0.
    """
    state_file = storage_path / "STATE.json"

    if state_file.exists():
        try:
            state_doc = json.loads(state_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state_doc = {}
        current_state = state_doc.get("current", flow["states"][0])
        conv = state_doc.get("current_conversation", 0)
    else:
        current_state = flow["states"][0]
        conv = 0

    feedback_dir = storage_path / "feedback"
    if feedback_dir.exists():
        open_feedback_files = [
            f.name for f in sorted(feedback_dir.iterdir()) if f.suffix == ".md"
        ]
    else:
        open_feedback_files = []

    limits = dict(_DEFAULT_LIMITS)
    top_limits = flow.get("limits")
    if top_limits:
        limits.update(top_limits)

    states_config = flow.get("states_config", {})
    if isinstance(states_config, dict):
        per_state = states_config.get(current_state, {})
        if isinstance(per_state, dict):
            per_state_limits = per_state.get("limits", {})
            if per_state_limits:
                limits.update(per_state_limits)

    return {
        "current_state": current_state,
        "conv": conv,
        "open_feedback_files": open_feedback_files,
        "limits": limits,
    }


def evaluate_transition_rules(
    flow: dict, current_state: str, storage_path: Path
) -> str | dict:
    """
    Evaluate routing rules for current_state in strict level order.
    Stop and return at the first match.

    Level 1 — on_artifact (dict or list):
      YAML format in this project: on_artifact is a dict {filename: next_state}.
      For each entry: if storage_path / filename exists → return next_state.

    Level 2 — on_content (list):
      For each entry: read storage_path / entry["file"] (skip if missing).
        If entry["contains"] is a substring of file contents → return entry["next"].
        If entry["regex"] is set, use re.search instead of substring check.

    Level 3 — decide (dict):
      Do NOT call LLM here. Return the decide dict as a sentinel:
        {"decide": True, "context_file": str, "question": str,
         "options": dict[str, str], "default": str}
      fsm.py never imports or calls any LLM SDK.

    Fallback — default (str):
      Return flow["transition_rules"][current_state]["default"] if present.
      Else return flow["transitions"][current_state][0].
      If neither exists: raise ValueError.

    If current_state has no transition_rules entry at all, fall back to
    flow["transitions"][current_state][0].
    """
    transition_rules = flow.get("transition_rules", {})

    if current_state not in transition_rules:
        transitions = flow.get("transitions", {})
        targets = transitions.get(current_state, [])
        if targets:
            return targets[0]
        raise ValueError(
            f"No transition rules or transitions defined for state: {current_state!r}"
        )

    rule = transition_rules[current_state]

    # Level 1 — on_artifact
    on_artifact = rule.get("on_artifact")
    if on_artifact is not None:
        if isinstance(on_artifact, dict):
            for filename, next_state in on_artifact.items():
                if (storage_path / filename).exists():
                    return next_state
        elif isinstance(on_artifact, list):
            for entry in on_artifact:
                if isinstance(entry, dict):
                    for filename, next_state in entry.items():
                        if (storage_path / filename).exists():
                            return next_state

    # Level 2 — on_content
    on_content = rule.get("on_content")
    if on_content:
        for entry in on_content:
            file_path = storage_path / entry["file"]
            if not file_path.exists():
                continue
            try:
                contents = file_path.read_text(encoding="utf-8")
            except OSError:
                continue
            if "regex" in entry:
                if re.search(entry["regex"], contents):
                    return entry["next"]
            elif "contains" in entry:
                if entry["contains"] in contents:
                    return entry["next"]

    # Level 3 — decide
    decide = rule.get("decide")
    if decide is not None:
        return {
            "decide": True,
            "context_file": decide.get("context_file", ""),
            "question": decide.get("question", ""),
            "options": decide.get("options", {}),
            "default": decide.get("default", ""),
        }

    # Fallback — default
    if "default" in rule:
        return rule["default"]

    transitions = flow.get("transitions", {})
    targets = transitions.get(current_state, [])
    if targets:
        return targets[0]

    raise ValueError(f"No default transition defined for state: {current_state!r}")


def route_feedback(flow: dict, storage_path: Path) -> dict | None:
    """
    Read *.md files in storage_path/feedback/.
    Apply priority order from flow["feedback_routing"] (dict, ordered by insertion):
      Keys earlier in the dict have higher priority.
    Return {"file": filename_with_ext, "target_agent": agent_name} for highest-priority match.
    If file is HUMAN_QUESTIONS.md or BLOCKED_ON_HUMAN.md, also include
      "instructions": <file contents>.
    Return None if feedback/ is empty or does not exist.
    """
    feedback_dir = storage_path / "feedback"
    if not feedback_dir.exists():
        return None

    md_files = {f.name for f in feedback_dir.iterdir() if f.suffix == ".md"}
    if not md_files:
        return None

    feedback_routing = flow.get("feedback_routing", {})
    human_files = {"HUMAN_QUESTIONS.md", "BLOCKED_ON_HUMAN.md"}

    for stem, agent in feedback_routing.items():
        filename = stem if stem.endswith(".md") else f"{stem}.md"
        if filename in md_files:
            result = {"file": filename, "target_agent": agent}
            if filename in human_files:
                try:
                    result["instructions"] = (feedback_dir / filename).read_text(
                        encoding="utf-8"
                    )
                except OSError:
                    result["instructions"] = ""
            return result

    return None


def run_transition_actions(
    flow: dict,
    prev_state: str,
    next_state: str,
    storage_path: Path,
    topic: str,
    conv: int,
) -> None:
    """
    Read flow["transition_actions"].
    Look up key "prev_state->next_state"; also check "->next_state" wildcard.
    For each matched action in YAML order, check action["skill"] field:
      "commit" or "git_commit": subprocess git add -A + git commit -m action["message"]
        Use cwd=str(storage_path.parent.parent.parent) (project root = 3 levels up from storage_path).
        If git exits with code indicating nothing to commit, treat as no-op (don't raise).
      "archive-artifacts" or "archive_artifacts": copy feedback/*.md to
        pathly/pipeline-walkthrough/<topic>/artifacts/<NAME>_conv<conv>_attempt<M>.md
        <M> = count of existing files in that dir matching <NAME>_conv<conv>_attempt*.md + 1
        Create dirs as needed.
      "update_progress": edit PROGRESS.md — mark conv row DONE (mark: conv_done)
        or all phases DONE (mark: all_phases_done).
    No-op if no key matches.
    On action failure: raise RuntimeError with description.
    """
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
            message = action.get(
                "message", f"chore: transition {prev_state}->{next_state}"
            )
            try:
                try:
                    add_result = subprocess.run(
                        ["git", "add", "-A"],
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
                        pass  # no-op
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
    # Scan all non-empty lines — the marker may appear after front-matter or headers.
    for line in text.splitlines():
        if line.strip() == marker:
            return True
    return False


def _write_gate_feedback(storage_path: Path, on_fail: str, reason: str) -> None:
    feedback_dir = storage_path / "feedback"
    feedback_dir.mkdir(parents=True, exist_ok=True)
    target = feedback_dir / on_fail
    target.write_text(reason, encoding="utf-8")


def _scope_clean(storage_path: Path, scope_file: str, baseline_sha: str | None) -> bool:
    import re as _re

    scope_path = storage_path / scope_file
    declared: set[str] = set()

    if scope_path.exists():
        try:
            text = scope_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        # Extract backtick-quoted tokens from each line individually so code-block
        # fences (``` ... ```) don't swallow adjacent inline paths.
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

    if not baseline_sha:
        append_event(
            storage_path,
            {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "no_baseline_sha"},
        )
        return True

    # Project root is 3 levels up from storage_path (pathly/plans/{topic}/)
    project_root = storage_path.parent.parent.parent

    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", baseline_sha],
            cwd=str(project_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        append_event(
            storage_path,
            {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "git_diff_failed"},
        )
        return True

    if result.returncode != 0:
        append_event(
            storage_path,
            {"type": "GATE_SKIPPED", "gate": "scope_gate", "reason": "git_diff_failed"},
        )
        return True

    # Paths automatically exempt from the scope gate regardless of declaration:
    # - pathly/plans/ — FSM-managed artifacts (EVENTS.jsonl, STATE.json, feedback/, etc.)
    # - *.tsbuildinfo — TypeScript incremental build cache, modified by typecheck runs
    def _is_exempt(p: str) -> bool:
        return (
            p.startswith("pathly/plans/")
            or p.startswith("src/pathly_orchestrator/")
            or p.endswith(".tsbuildinfo")
        )

    changed_paths = [p for p in result.stdout.splitlines() if p.strip()]
    for path in changed_paths:
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
) -> dict | None:
    gates = flow.get("gates", {})
    # Gates are evaluated fail-fast: stop at the first failure so feedback is unambiguous.
    applicable = gates.get(f"{prev_state}->{next_state}", []) + gates.get(
        f"->{next_state}", []
    )
    # Read conv_start_sha once for scope_gate use
    state_file = storage_path / "STATE.json"
    conv_start_sha: str | None = None
    if state_file.exists():
        try:
            state_doc = json.loads(state_file.read_text(encoding="utf-8"))
            conv_start_sha = state_doc.get("conv_start_sha") or None
        except (json.JSONDecodeError, OSError):
            pass

    for gate in applicable:
        gtype = gate["type"]
        if gtype == "require_artifact":
            artifact_path = storage_path / gate["artifact"]
            if not artifact_path.exists():
                reason = f"Required artifact missing: {gate['artifact']}"
                _write_gate_feedback(storage_path, gate["on_fail"], reason)
                append_event(
                    storage_path,
                    {
                        "type": "GATE_FAILED",
                        "gate": gtype,
                        "transition": f"{prev_state}->{next_state}",
                    },
                )
                return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        elif gtype == "verify_gate":
            artifact_path = storage_path / gate["artifact"]
            marker = gate["pass_marker"]
            if not _verify_passed(artifact_path, marker):
                reason = f"Gate verification failed: {gate['artifact']} does not start with {marker!r}"
                _write_gate_feedback(storage_path, gate["on_fail"], reason)
                append_event(
                    storage_path,
                    {
                        "type": "GATE_FAILED",
                        "gate": gtype,
                        "transition": f"{prev_state}->{next_state}",
                    },
                )
                return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        elif gtype == "scope_gate":
            scope_file = gate["scope_file"]
            if not _scope_clean(storage_path, scope_file, conv_start_sha):
                reason = f"Scope gate failed: changes outside declared scope in {scope_file}"
                _write_gate_feedback(storage_path, gate["on_fail"], reason)
                append_event(
                    storage_path,
                    {
                        "type": "GATE_FAILED",
                        "gate": gtype,
                        "transition": f"{prev_state}->{next_state}",
                    },
                )
                return {"gate_failed": gtype, "feedback_file": gate["on_fail"]}
        else:
            raise RuntimeError(f"Unknown gate type: {gtype!r}")
    return None


def write_state(storage_path: Path, next_state: str, prior_state: dict) -> None:
    """
    Write STATE.json atomically (write to .tmp then rename).
    Preserve all fields from prior_state; overwrite "current" with next_state.
    Create storage_path if it does not exist.
    """
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
