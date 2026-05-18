"""
pathly-ff — fast-forward to the next FSM state without running the current stage agent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from pathly_orchestrator.mcp_server import _complete_stage, _next_action


_SCAN_ROOTS = [
    ("pathly/plans", "team"),
    ("pathly/debugs", "debug"),
    ("pathly/explorations", "explore"),
]


def _find_most_recent_state(cwd: Path) -> tuple[Path, str, str] | None:
    best_mtime = -1.0
    best: tuple[Path, str, str] | None = None

    for root_rel, flow in _SCAN_ROOTS:
        root = cwd / root_rel
        if not root.is_dir():
            continue
        for state_file in root.glob("*/STATE.json"):
            if ".archive" in str(state_file):
                continue
            mtime = state_file.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best = (state_file.parent, state_file.parent.name, flow)

    return best


def _find_topic_dir(cwd: Path, topic: str) -> tuple[Path, str] | None:
    for root_rel, flow in _SCAN_ROOTS:
        root = cwd / root_rel
        candidate = root / topic
        if (candidate / "STATE.json").exists():
            return candidate, flow
    return None


def _has_git_commit_action(flow_config: dict, state_name: str) -> bool:
    state_cfg = flow_config.get("states", {}).get(state_name, {})
    for key in ("transition_rules", "transition_actions"):
        items = state_cfg.get(key, [])
        if isinstance(items, list):
            for item in items:
                item_str = str(item)
                if "git_commit" in item_str:
                    return True
        elif isinstance(items, dict):
            for v in items.values():
                if "git_commit" in str(v):
                    return True
    return False


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pathly-ff",
        description="Fast-forward to the next FSM state without running the current stage agent.",
    )
    parser.add_argument(
        "topic",
        nargs="?",
        help="Feature topic name (defaults to most recently modified).",
    )
    args = parser.parse_args()

    cwd = Path.cwd()

    if args.topic:
        result = _find_topic_dir(cwd, args.topic)
        if result is None:
            print(f"Topic '{args.topic}' not found in any scan root.")
            sys.exit(1)
        storage_path, flow = result
        topic = args.topic
    else:
        found = _find_most_recent_state(cwd)
        if found is None:
            print("No active features found.")
            sys.exit(1)
        storage_path, topic, flow = found

    project_root = str(cwd)

    next_result = _next_action({"flow": flow, "topic": topic, "project_root": project_root})

    if next_result.get("blocked"):
        print(f"Blocked: {next_result}")
        print("Use pathly-fix first.")
        sys.exit(1)

    current_state = next_result["current_state"]

    try:
        from importlib.resources import files
        text = files("pathly_data").joinpath(f"core/flows/{flow}.flow.yaml").read_text(encoding="utf-8")
        flow_config = yaml.safe_load(text)
        if _has_git_commit_action(flow_config, current_state):
            print("! This transition may include a git commit.")
            answer = input("Proceed without running the current agent? (y/n): ").strip().lower()
            if answer != "y":
                print("Aborted.")
                sys.exit(0)
    except Exception:
        pass

    result = _complete_stage({"flow": flow, "topic": topic, "project_root": project_root})

    if result.get("decide"):
        print("FSM needs a routing decision:")
        print(f"  Question: {result['question']}")
        if result.get("context"):
            print(f"  Context:\n{result['context'][:500]}")
        opts = result.get("options", {})
        print(f"  Options: {', '.join(opts.keys())}")
        decision = input(f"  Your choice [{'/'.join(opts.keys())}]: ").strip()
        result = _complete_stage(
            {"flow": flow, "topic": topic, "project_root": project_root, "decision": decision}
        )

    if result.get("done"):
        print("Feature complete.")
        sys.exit(0)

    if result.get("blocked"):
        print("Blocked by feedback:")
        print(result)
        sys.exit(1)

    print(f"Advanced to: {result['next_state']}  Agent: {result.get('agent', '?')}")
    print("Run /pathly go to continue with the next agent.")
