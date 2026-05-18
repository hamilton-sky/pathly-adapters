"""pathly-run — autonomous FSM runner. Entry point: main()."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml
from importlib.resources import files

from pathly_orchestrator.mcp_server import _next_action, _complete_stage


def _storage_path(flow: str, project_root: str, topic: str) -> Path:
    text = files("pathly_data").joinpath(f"core/flows/{flow}.flow.yaml").read_text(encoding="utf-8")
    flow_config = yaml.safe_load(text)
    template = flow_config["storage_path"]
    return Path(project_root) / template.format(topic=topic)


def invoke_agent(
    instructions: str,
    project_root: str,
    model: str,
    state: str = "",
    topic: str = "",
    timeout: int = 600,
) -> None:
    prompt = (
        f"You are running pathly stage {state!r} for topic {topic!r}.\n\n"
        f"{instructions}"
    )
    cmd = [
        "claude",
        "-p", prompt,
        "--model", model,
        "--dangerously-skip-permissions",
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    try:
        return_code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Claude subprocess timed out after {timeout}s")
    if return_code != 0:
        raise RuntimeError(f"Claude subprocess exited with code {return_code}")


def handle_blocked(response: dict) -> None:
    if response.get("target_agent") == "human":
        print(f"\n⚠  Human checkpoint:\n{response.get('instructions', '')}\nFile: {response['file']}")
    else:
        print(f"⚠ Blocked on {response['file']} → routed to {response.get('target_agent')}")


def handle_decide(flow: str, topic: str, project_root: str, response: dict) -> dict:
    print(f"\n? {response['question']}")
    for key, value in response.get("options", {}).items():
        print(f"  [{key}] {value}")
    default = response.get("default", "")
    chosen = input(f"Choice (default: {default}): ").strip()
    if not chosen or chosen not in response.get("options", {}):
        chosen = default
    return _complete_stage({
        "flow": flow,
        "topic": topic,
        "project_root": project_root,
        "decision": chosen,
    })


def resolve_stage(
    flow: str,
    topic: str,
    project_root: str,
    model: str,
    state: str,
    timeout: int = 600,
) -> dict:
    resolved: list[str] = []
    feedback_rounds = 0
    MAX_FEEDBACK_ROUNDS = 3

    while True:
        result = _complete_stage({
            "flow": flow,
            "topic": topic,
            "project_root": project_root,
            "resolved_files": resolved or None,
        })
        resolved = []

        if result.get("done") or result.get("next_state"):
            return result

        if result.get("decide"):
            return handle_decide(flow, topic, project_root, result)

        if result.get("blocked"):
            target = result["target_agent"]
            file = result["file"]

            if target == "human":
                print(f"\n⚠  Human checkpoint — {file}")
                print(result.get("instructions", "(see file)"))
                input("\nPress Enter when resolved: ")
                resolved = [file]
                continue

            feedback_rounds += 1
            if feedback_rounds > MAX_FEEDBACK_ROUNDS:
                print(f"⚠  Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file}. Escalating to human.")
                storage = _storage_path(flow, project_root, topic)
                escalation = storage / "feedback" / "HUMAN_QUESTIONS.md"
                escalation.parent.mkdir(parents=True, exist_ok=True)
                escalation.write_text(
                    f"# Escalation\nFeedback file `{file}` was not resolved after {MAX_FEEDBACK_ROUNDS} attempts.\n"
                )
                input("\nPress Enter when resolved: ")
                resolved = ["HUMAN_QUESTIONS.md"]
                feedback_rounds = 0
                continue

            print(f"\n↩  Feedback: {file}  →  resolving with {target}")
            fb_instructions = result.get("instructions", f"Resolve feedback in feedback/{file}")
            invoke_agent(fb_instructions, project_root, model, state=f"resolving {file}", topic=topic, timeout=timeout)
            resolved = [file]
            continue

        return result


def run_flow(
    flow: str,
    topic: str,
    project_root: str,
    rigor: str = "standard",
    model: str = "claude-sonnet-4-6",
    timeout: int = 600,
) -> int:
    print(f"── pathly-run ──  flow={flow}  topic={topic}  project_root={project_root}")

    while True:
        try:
            response = _next_action({"flow": flow, "topic": topic, "project_root": project_root})
        except RuntimeError as exc:
            print(str(exc))
            return 1

        if response.get("blocked"):
            handle_blocked(response)
            return 1

        current_state = response.get("current_state", "")
        agent = response.get("agent", "")
        print(f"── [{current_state}] agent: {agent} ──")

        try:
            invoke_agent(
                response.get("instructions", ""),
                project_root,
                model,
                state=current_state,
                topic=topic,
                timeout=timeout,
            )
        except RuntimeError as exc:
            print(str(exc))
            return 1

        try:
            result = resolve_stage(flow, topic, project_root, model, current_state, timeout)
        except RuntimeError as exc:
            print(str(exc))
            return 1

        if result.get("done"):
            print("✓ Complete")
            return 0

        if result.get("next_state"):
            print(f"✓ {current_state} → {result['next_state']}")
            continue

        if result.get("blocked"):
            handle_blocked(result)
            return 1

        print(f"⚠ Unexpected result: {result}")
        return 1


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Autonomous pathly FSM runner")
    parser.add_argument("topic")
    parser.add_argument("--flow", default="team")
    parser.add_argument("--rigor", default="standard", choices=["lite", "standard", "strict"])
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--timeout", default=600, type=int)
    args = parser.parse_args()
    project_root = args.project_root or str(Path.cwd())
    sys.exit(run_flow(args.flow, args.topic, project_root, args.rigor, args.model, args.timeout))
