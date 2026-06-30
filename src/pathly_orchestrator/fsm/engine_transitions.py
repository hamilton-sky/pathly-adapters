"""FSM transition evaluation and feedback routing."""

from __future__ import annotations

import json
import re
from pathlib import Path

# Feedback escalation attempt threshold for a single-target (string) escalation.
_ESCALATE_AT_ATTEMPT = 3

_COMPARE_OPS = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "eq": lambda a, b: a == b,
    "gte": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "ne": lambda a, b: a != b,
}


def evaluate_transition_rules(
    flow: dict, current_state: str, storage_path: Path, *, goal_id: str | None = None
) -> str | dict:
    """Evaluate routing rules for current_state in strict level order.

    Level 1 — on_artifact: if storage_path/filename exists → return next_state.
    Level 2 — on_content: substring/regex match in a file → return next_state.
    Level 2.5 — on_state_counter: numeric DB field comparison.
    Level 2.6 — on_board_count: goal-scoped board task-count gate (Fix B).
    Level 3 — decide: return sentinel dict (no LLM call).
    Fallback — default or first transition.
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

    # Level 2.5 — on_state_counter
    on_state_counter = rule.get("on_state_counter")
    if on_state_counter is not None:
        field = on_state_counter.get("field")
        op = on_state_counter.get("op")
        compare_to = on_state_counter.get("compare_to")
        next_s = on_state_counter.get("next")
        op_fn = _COMPARE_OPS.get(op)
        if op_fn is not None and field and compare_to and next_s:
            try:
                from pathly_orchestrator import eventlog as _eventlog

                state_doc = _eventlog.read_state(str(storage_path)) or {}
                field_val = int(state_doc[field])
                compare_val = int(state_doc[compare_to])
                if op_fn(field_val, compare_val):
                    return next_s
            except (KeyError, ValueError, TypeError):
                pass

    # Level 2.6 — on_board_count (goal-scoped board task-count gate; Fix B)
    on_board_count = rule.get("on_board_count")
    if on_board_count is not None and goal_id is not None:
        op = on_board_count.get("op")
        compare_to = on_board_count.get("compare_to")
        next_s = on_board_count.get("next")
        op_fn = _COMPARE_OPS.get(op)
        # compare_to read as a raw int; `is not None` so compare_to=0 is honored
        if op_fn is not None and compare_to is not None and next_s:
            try:
                from pathly_orchestrator.db.connection import get_db
                from pathly_orchestrator.db.queries.comms_tasks import count_tasks_for_goal
                count = count_tasks_for_goal(get_db(), goal_id)
                if op_fn(count, int(compare_to)):
                    return next_s
            except Exception:
                pass  # DB error → fail-closed: do NOT advance

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


def _normalize_tiers(spec) -> list[tuple[int, str]]:
    """Normalize an escalation_routing value into sorted (attempt, role) tiers.

    Forms: "planner" → [(3, planner)]; ["planner", "architect"] → [(3, planner), (4, architect)];
    [{at: 3, to: planner}, {at: 5, to: architect}] → explicit thresholds.
    """
    if isinstance(spec, str):
        return [(_ESCALATE_AT_ATTEMPT, spec)]
    tiers: list[tuple[int, str]] = []
    if isinstance(spec, list):
        for i, item in enumerate(spec):
            if isinstance(item, str):
                tiers.append((_ESCALATE_AT_ATTEMPT + i, item))
            elif isinstance(item, dict):
                at = item.get("at", item.get("after"))
                to = item.get("to", item.get("agent"))
                if isinstance(at, int) and isinstance(to, str):
                    tiers.append((at, to))
    tiers.sort(key=lambda t: t[0])
    return tiers


def _resolve_feedback_target(
    filename: str, base_agent: str, retry_count: int, escalation_routing: dict
) -> str:
    """Map (feedback file, retry count) → role that should handle it per escalation tiers."""
    stem = filename[:-3] if filename.endswith(".md") else filename
    esc = escalation_routing or {}
    spec = esc.get(stem)
    if spec is None:
        spec = esc.get(filename)
    if spec is None:
        return base_agent
    tiers = _normalize_tiers(spec)
    if not tiers:
        return base_agent
    attempt = (retry_count or 0) + 1
    if attempt < tiers[0][0]:
        return base_agent
    if attempt > tiers[-1][0]:
        return "human"
    target = base_agent
    for at, to in tiers:
        if attempt >= at:
            target = to
        else:
            break
    return target


def _read_retry_counts(storage_path: Path) -> dict[str, int]:
    """{FILENAME.md: max retry count} from STATE.json retry_count_by_key. Best-effort."""
    out: dict[str, int] = {}
    try:
        raw = json.loads((storage_path / "STATE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return out
    for key, count in (raw.get("retry_count_by_key") or {}).items():
        fname = key.split(":", 1)[1] if ":" in key else key
        try:
            out[fname] = max(out.get(fname, 0), int(count or 0))
        except (TypeError, ValueError):
            continue
    return out


def route_feedback(
    flow: dict, storage_path: Path, *, retry_counts: dict | None = None
) -> dict | None:
    """Return the highest-priority open feedback entry, or None if feedback/ is empty.

    Side-effect: syncs found/resolved files to the feedback_items DB table.
    """
    feedback_dir = storage_path / "feedback"
    if not feedback_dir.exists():
        return None

    md_files = {f.name for f in feedback_dir.iterdir() if f.suffix == ".md"}

    # Sync to DB — best-effort, never blocks routing.
    try:
        from pathly_orchestrator.db import (
            get_db,
            read_feedback_items,
            resolve_feedback_item,
            write_feedback_item,
        )

        _conn = get_db()
        _feature = storage_path.name
        _project_root = str(storage_path.parent.parent.parent)
        for _fname in md_files:
            _content: str | None = None
            try:
                _content = (feedback_dir / _fname).read_text(encoding="utf-8")
            except OSError:
                pass
            write_feedback_item(_conn, _project_root, _feature, _fname, _content)
        for _item in read_feedback_items(_conn, _project_root, _feature):
            if _item["filename"] not in md_files:
                resolve_feedback_item(_conn, _project_root, _feature, _item["filename"])
    except Exception:
        pass

    if not md_files:
        return None

    feedback_routing = flow.get("feedback_routing", {})
    escalation_routing = flow.get("escalation_routing", {})
    human_files = {"HUMAN_QUESTIONS.md", "BLOCKED_ON_HUMAN.md"}
    counts = (
        retry_counts if retry_counts is not None else _read_retry_counts(storage_path)
    )

    known_filenames: set[str] = set()
    for stem, agent in feedback_routing.items():
        filename = stem if stem.endswith(".md") else f"{stem}.md"
        known_filenames.add(filename)
        if filename in md_files:
            target = _resolve_feedback_target(
                filename, agent, counts.get(filename, 0), escalation_routing
            )
            result = {"file": filename, "target_agent": target}
            if target == "human" or filename in human_files:
                try:
                    result["instructions"] = (feedback_dir / filename).read_text(
                        encoding="utf-8"
                    )
                except OSError:
                    result["instructions"] = ""
            return result

    unmatched = md_files - known_filenames
    if unmatched:
        filename = sorted(unmatched)[0]
        return {
            "file": filename,
            "target_agent": "human",
            "instructions": f"Unrecognized feedback file: {filename}. Review and resolve manually.",
        }

    return None
