"""
pathly-status — cross-feature dashboard for active Pathly flows.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

# Ensure stdout can handle Unicode on Windows (cp1252 terminals)
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-16"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

_FEEDBACK_PRIORITY = [
    "HUMAN_QUESTIONS",
    "BLOCKED_ON_HUMAN",
    "ARCH_FEEDBACK",
    "DESIGN_QUESTIONS",
    "IMPL_QUESTIONS",
    "REVIEW_FAILURES",
    "TEST_FAILURES",
]

from pathly_orchestrator.cli._discovery import iter_state_files

_SEP = "─" * 57


def _find_feedback(feature_dir: Path) -> str | None:
    feedback_dir = feature_dir / "feedback"
    if not feedback_dir.is_dir():
        return None
    files = list(feedback_dir.glob("*.md"))
    if not files:
        return None

    names = [f.stem for f in files]

    highest = None
    for priority_name in _FEEDBACK_PRIORITY:
        for name in names:
            if name.startswith(priority_name):
                highest = priority_name
                break
        if highest:
            break

    if highest is None:
        highest = names[0]

    extra = len(files) - 1
    if extra > 0:
        return f"{highest} (+{extra} more)"
    return highest


def _scan(cwd: Path) -> tuple[list[dict], list[dict]]:
    active: list[dict] = []
    done: list[dict] = []

    for state_file, flow in iter_state_files(cwd):
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        topic = state_file.parent.name
        state = data.get("current", "UNKNOWN")
        conv = data.get("current_conversation", 0)
        mtime = state_file.stat().st_mtime
        feedback = _find_feedback(state_file.parent)

        entry = {
            "topic": topic,
            "flow": flow,
            "state": state,
            "conv": conv,
            "mtime": mtime,
            "feedback": feedback,
        }

        if state == "DONE":
            done.append(entry)
        else:
            active.append(entry)

    active.sort(key=lambda e: e["mtime"], reverse=True)
    return active, done


def _render_row(entry: dict) -> str:
    topic = entry["topic"]
    flow = entry["flow"]
    state = entry["state"]
    conv = entry["conv"]
    feedback = entry["feedback"]

    topic_col = topic.ljust(20)
    flow_col = flow.ljust(8)
    state_col = state.ljust(16)

    if feedback:
        suffix = f"[BLOCKED: {feedback}]"
    else:
        suffix = f"(conv {conv})"

    return f"  {topic_col} ·  {flow_col} ·  {state_col} {suffix}"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pathly-status",
        description="Show active Pathly features.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Also show DONE features.",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    active, done = _scan(cwd)

    print(_SEP)
    print("  Pathly · Active features")
    print(_SEP)

    if not active:
        print("  Nothing in progress.")
    else:
        for entry in active:
            print(_render_row(entry))

    if args.show_all and done:
        print(_SEP)
        print("  Completed features")
        print(_SEP)
        for entry in done:
            topic = entry["topic"]
            flow = entry["flow"]
            print(f"  {topic.ljust(20)} ·  {flow.ljust(8)} ·  DONE             ✓")

    print(_SEP)
    sys.exit(0)
