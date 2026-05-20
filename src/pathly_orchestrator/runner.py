"""pathly-run — autonomous FSM runner. Entry point: main()."""
from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("pathly.runner")

import yaml
from importlib.resources import files

from pathly_orchestrator.fsm_ops import next_action, complete_stage


def _storage_path(flow: str, project_root: str, topic: str) -> Path:
    text = files("pathly_data").joinpath(f"core/flows/{flow}.flow.yaml").read_text(encoding="utf-8")
    flow_config = yaml.safe_load(text)
    template = flow_config["storage_path"]
    return Path(project_root) / template.format(topic=topic)


def _patch_last_agent_done(storage_path: Path, cost_usd: float, tokens_in: int, tokens_out: int, wall_seconds: int, tool_uses: int = 0) -> None:
    """Find the last AGENT_DONE line in EVENTS.jsonl and fill in real cost/token/tool data."""
    events_file = storage_path / "EVENTS.jsonl"
    if not events_file.exists():
        return
    lines = events_file.read_text(encoding="utf-8").splitlines()
    patched = False
    for i in range(len(lines) - 1, -1, -1):
        try:
            ev = json.loads(lines[i])
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "AGENT_DONE":
            ev["cost_usd"] = cost_usd
            ev["tokens_in"] = tokens_in
            ev["tokens_out"] = tokens_out
            ev["wall_seconds"] = wall_seconds
            ev["tool_uses"] = tool_uses
            lines[i] = json.dumps(ev)
            patched = True
            break
    if patched:
        events_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def invoke_agent(
    instructions: str,
    project_root: str,
    model: str,
    state: str = "",
    topic: str = "",
    timeout: int = 600,
    storage_path: Path | None = None,
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
        "--output-format", "json",
    ]
    t_start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )
    try:
        stdout_bytes, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError(f"Claude subprocess timed out after {timeout}s")

    wall_seconds = int(time.monotonic() - t_start)

    if proc.returncode != 0:
        raise RuntimeError(f"Claude subprocess exited with code {proc.returncode}")

    # Parse JSON output for cost + token counts
    cost_usd = 0.0
    tokens_in = 0
    tokens_out = 0
    tool_uses = 0
    try:
        output = json.loads(stdout_bytes.decode("utf-8", errors="replace"))
        # Try every field name Claude CLI has used across versions
        cost_usd = float(
            output.get("cost_usd")
            or output.get("total_cost_usd")
            or output.get("totalCost")
            or output.get("total_cost")
            or 0.0
        )
        usage = output.get("usage") or output.get("inputUsage") or {}
        tokens_in  = int(
            (usage.get("input_tokens") or usage.get("inputTokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
        )
        tokens_out = int(usage.get("output_tokens", 0) or usage.get("outputTokens", 0))
        # Count tool_use content blocks across all messages in the conversation
        messages = output.get("messages", [])
        for msg in messages:
            for block in msg.get("content", []) if isinstance(msg.get("content"), list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_uses += 1
        # Print the agent's text result so the terminal isn't silent
        result_text = output.get("result", "")
        if result_text:
            print(result_text)
        # Diagnostic: always log telemetry so we can verify it's being captured
        logger.info("telemetry", extra={"cost_usd": cost_usd, "tokens_in": tokens_in, "tokens_out": tokens_out, "tool_uses": tool_uses, "wall_seconds": wall_seconds})
        if cost_usd == 0.0:
            top_keys = [k for k in output if k not in ("result", "messages", "session_id")]
            logger.warning("cost=0 — JSON top-level keys: %s", top_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("failed to parse claude JSON output: %s", exc)

    # Patch the AGENT_DONE event the agent wrote with real numbers
    if storage_path:
        _patch_last_agent_done(storage_path, cost_usd, tokens_in, tokens_out, wall_seconds, tool_uses)


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
    return complete_stage({
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
    storage_path: Path | None = None,
) -> dict:
    resolved: list[str] = []
    feedback_rounds = 0
    MAX_FEEDBACK_ROUNDS = 3

    while True:
        result = complete_stage({
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
            invoke_agent(fb_instructions, project_root, model, state=f"resolving {file}", topic=topic, timeout=timeout, storage_path=storage_path)
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
    storage = _storage_path(flow, project_root, topic)

    while True:
        try:
            response = next_action({"flow": flow, "topic": topic, "project_root": project_root})
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
                storage_path=storage,
            )
        except RuntimeError as exc:
            print(str(exc))
            return 1

        try:
            result = resolve_stage(flow, topic, project_root, model, current_state, timeout, storage_path=storage)
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
