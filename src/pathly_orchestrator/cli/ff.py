"""
pathly-ff — fast-forward to the next FSM state without running the current stage agent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from pathly_orchestrator.fsm_http_client import complete_stage, next_action

from pathly_orchestrator.cli._discovery import (
    find_most_recent_state as _find_most_recent_state,
    find_topic_dir as _find_topic_dir,
)


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

    next_result = next_action(
        {"flow": flow, "topic": topic, "project_root": project_root}
    )

    if next_result.get("blocked"):
        print(f"Blocked: {next_result}")
        print("Use pathly-fix first.")
        sys.exit(1)

    current_state = next_result["current_state"]

    try:
        from importlib.resources import files

        text = (
            files("pathly_data")
            .joinpath(f"core/flows/{flow}.flow.yaml")
            .read_text(encoding="utf-8")
        )
        flow_config = yaml.safe_load(text)
        if _has_git_commit_action(flow_config, current_state):
            print("! This transition may include a git commit.")
            answer = (
                input("Proceed without running the current agent? (y/n): ")
                .strip()
                .lower()
            )
            if answer != "y":
                print("Aborted.")
                sys.exit(0)
    except Exception:
        pass

    cs_result: dict = complete_stage(
        {"flow": flow, "topic": topic, "project_root": project_root}
    )

    if cs_result.get("decide"):
        print("FSM needs a routing decision:")
        print(f"  Question: {cs_result['question']}")
        if cs_result.get("context"):
            print(f"  Context:\n{cs_result['context'][:500]}")
        opts = cs_result.get("options", {})
        print(f"  Options: {', '.join(opts.keys())}")
        decision = input(f"  Your choice [{'/'.join(opts.keys())}]: ").strip()
        cs_result = complete_stage(
            {
                "flow": flow,
                "topic": topic,
                "project_root": project_root,
                "decision": decision,
            }
        )

    if cs_result.get("done"):
        print("Feature complete.")
        sys.exit(0)

    if cs_result.get("blocked"):
        print("Blocked by feedback:")
        print(cs_result)
        sys.exit(1)

    print(
        f"Advanced to: {cs_result['next_state']}  Agent: {cs_result.get('agent', '?')}"
    )
    print("Run /pathly go to continue with the next agent.")
    sys.exit(0)
