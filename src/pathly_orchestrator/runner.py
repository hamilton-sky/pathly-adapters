"""pathly-run — autonomous FSM runner. Entry point: main()."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger("pathly.runner")

import yaml
from importlib.resources import files

from pathly_orchestrator.adapters import resolve_command
from pathly_orchestrator.fsm_http_client import next_action, complete_stage

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def _storage_path(flow: str, project_root: str, topic: str) -> Path:
    text = (
        files("pathly_data")
        .joinpath(f"core/flows/{flow}.flow.yaml")
        .read_text(encoding="utf-8")
    )
    flow_config = yaml.safe_load(text)
    template = flow_config["storage_path"]
    return Path(project_root) / template.format(topic=topic)


def resolve_argv(
    adapter: str,
    prompt: str,
    model: str,
    session: str | None = None,
    autonomy: bool = True,
) -> list[str]:
    argv = resolve_command(
        adapter,
        prompt,
        model,
        session=session,
        autonomy=autonomy,
    )["argv"]
    if adapter == "claude" and "--output-format=json" not in argv:
        argv = [*argv, "--print", "--output-format=json"]
    return argv


def _extract_json_payload(raw_output: str) -> dict[str, Any]:
    cleaned = _ANSI_RE.sub("", raw_output or "").strip()
    if not cleaned:
        return {}
    decoder = json.JSONDecoder()
    last: dict[str, Any] = {}
    for idx in range(len(cleaned)):
        if cleaned[idx] not in "{[":
            continue
        try:
            payload, _ = decoder.raw_decode(cleaned, idx)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            last = payload
    return last


def parse_result(adapter: str, raw_output: str) -> dict[str, Any]:
    payload = _extract_json_payload(raw_output)
    if adapter == "codex":
        cost = payload.get("cost_usd", payload.get("cost", 0.0))
        session_id = payload.get("session_id") or payload.get("sessionId")
    else:
        cost = (
            payload.get("cost_usd")
            or payload.get("total_cost_usd")
            or payload.get("totalCost")
            or payload.get("total_cost")
            or 0.0
        )
        session_id = payload.get("session_id") or payload.get("sessionId")
    try:
        cost_usd = float(cost or 0.0)
    except (TypeError, ValueError):
        cost_usd = 0.0

    # Extract AskUserQuestion denial if present
    permission_denials = payload.get("permission_denials") or []
    ask_user_question = None
    for denial in (permission_denials if isinstance(permission_denials, list) else []):
        if isinstance(denial, dict) and denial.get("tool_name") == "AskUserQuestion":
            ask_user_question = denial
            break

    return {
        "cost_usd": cost_usd,
        "session_id": session_id or None,
        "ask_user_question": ask_user_question,
        "result": payload.get("result", ""),
    }


def _patch_last_agent_done(
    storage_path: Path,
    cost_usd: float,
    tokens_in: int,
    tokens_out: int,
    wall_seconds: int,
    tool_uses: int = 0,
) -> None:
    """Find the last AGENT_DONE line in EVENTS.jsonl and fill in real cost/token/tool data."""
    events_file = storage_path / "EVENTS.jsonl"
    if not events_file.exists():
        return
    lines = events_file.read_text(encoding="utf-8").splitlines()
    patched = False
    patched_agent: str | None = None
    patched_conv: int | None = None
    for i in range(len(lines) - 1, -1, -1):
        try:
            ev = json.loads(lines[i])
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "AGENT_DONE":
            patched_agent = ev.get("agent")
            patched_conv = ev.get("conversation")
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
        # Append BILLING_UPDATE so the SSE forward-tailer re-broadcasts corrected values.
        billing: dict[str, object] = {
            "type": "BILLING_UPDATE",
            "agent": patched_agent,
            "conversation": patched_conv,
            "cost_usd": cost_usd,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "total_tokens": tokens_in + tokens_out,
            "wall_seconds": wall_seconds,
            "tool_uses": tool_uses,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(events_file, "a", encoding="utf-8") as _f:
            _f.write(json.dumps(billing) + "\n")


def read_last_agent_done(storage_path: Path) -> dict[str, Any] | None:
    """Return the last AGENT_DONE event from EVENTS.jsonl, or None if absent."""
    events_file = storage_path / "EVENTS.jsonl"
    if not events_file.exists():
        return None
    try:
        lines = events_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "AGENT_DONE":
            return ev
    return None


def tail_agent_done(
    path: str,
    after_ts: str,
    stop_evt: threading.Event,
    poll_interval: float = 0.1,
) -> Generator[dict, None, None]:
    """
    Tail EVENTS.jsonl and yield AGENT_DONE events with ts >= after_ts.
    Tracks byte offset so no event is yielded twice.
    Stops when stop_evt is set and no new bytes remain.
    Does not raise if the file does not exist yet — waits until it does.
    """
    offset = 0
    while True:
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                new_bytes = f.read()
        except OSError:
            new_bytes = b""
        if new_bytes:
            offset += len(new_bytes)
            for raw_line in new_bytes.split(b"\n"):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "AGENT_DONE" and event.get("ts", "") >= after_ts:
                    yield event
            time.sleep(poll_interval)
        else:
            if stop_evt.is_set():
                return
            time.sleep(poll_interval)


def invoke_agent(
    instructions: str,
    project_root: str,
    model: str,
    state: str = "",
    topic: str = "",
    timeout: int = 600,
    storage_path: Path | None = None,
    adapter: str = "claude",
    session: str | None = None,
    autonomy: bool = True,
    _abort_ref=None,
) -> dict[str, Any]:
    """Invoke an adapter subprocess and return {cost_usd, session_id}.

    _abort_ref: optional RunnerState-like object; if its _abort_flag is set,
    the subprocess is killed and RuntimeError('aborted') is raised.
    """
    prompt = (
        f"You are running pathly stage {state!r} for topic {topic!r}.\n\n"
        f"{instructions}"
    )
    cmd = resolve_argv(adapter, prompt, model, session=session, autonomy=autonomy)
    t_start = time.monotonic()
    proc = subprocess.Popen(
        cmd,
        cwd=project_root,
        stdout=subprocess.PIPE,
        stderr=sys.stderr,
    )
    if _abort_ref is not None:
        # Store proc reference so abort_run() can kill it
        try:
            from pathly_orchestrator import supervisor as _sup
            with _sup._lock:
                _abort_ref._proc = proc
        except Exception:
            pass

    stdout_bytes: bytes = b""
    try:
        # Poll for abort while waiting for the subprocess
        if _abort_ref is not None:
            while True:
                try:
                    stdout_bytes, _ = proc.communicate(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    abort_now = False
                    try:
                        from pathly_orchestrator import supervisor as _sup
                        with _sup._lock:
                            abort_now = _abort_ref._abort_flag
                    except Exception:
                        pass
                    if abort_now:
                        proc.kill()
                        try:
                            from pathly_orchestrator import supervisor as _sup
                            with _sup._lock:
                                _abort_ref._proc = None
                        except Exception:
                            pass
                        raise RuntimeError("aborted")
                    # Check overall timeout
                    if time.monotonic() - t_start > timeout:
                        proc.kill()
                        raise RuntimeError(f"Claude subprocess timed out after {timeout}s")
        else:
            try:
                stdout_bytes, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RuntimeError(f"Claude subprocess timed out after {timeout}s")
    finally:
        if _abort_ref is not None:
            try:
                from pathly_orchestrator import supervisor as _sup
                with _sup._lock:
                    _abort_ref._proc = None
            except Exception:
                pass

    wall_seconds = int(time.monotonic() - t_start)

    if proc.returncode != 0:
        raise RuntimeError(f"Claude subprocess exited with code {proc.returncode}")

    # Parse JSON output for cost + token counts + session_id
    cost_usd = 0.0
    tokens_in = 0
    tokens_out = 0
    tool_uses = 0
    session_id_out: str | None = None
    try:
        raw_text = stdout_bytes.decode("utf-8", errors="replace")
        parsed = parse_result(adapter, raw_text)
        output = _extract_json_payload(raw_text)
        # Try every field name Claude CLI has used across versions
        cost_usd = float(parsed.get("cost_usd", 0.0) or 0.0)
        session_id_out = parsed.get("session_id") or None
        usage = output.get("usage") or output.get("inputUsage") or {}
        tokens_in = int(
            (usage.get("input_tokens") or usage.get("inputTokens") or 0)
            + (usage.get("cache_read_input_tokens") or 0)
            + (usage.get("cache_creation_input_tokens") or 0)
        )
        tokens_out = int(usage.get("output_tokens", 0) or usage.get("outputTokens", 0))
        # Count tool_use content blocks across all messages in the conversation
        messages = output.get("messages", [])
        for msg in messages:
            for block in (
                msg.get("content", []) if isinstance(msg.get("content"), list) else []
            ):
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_uses += 1
        # Print the agent's text result so the terminal isn't silent
        result_text = output.get("result", "")
        if result_text:
            print(result_text)
        # Diagnostic: always log telemetry so we can verify it's being captured
        logger.info(
            "telemetry",
            extra={
                "cost_usd": cost_usd,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "tool_uses": tool_uses,
                "wall_seconds": wall_seconds,
            },
        )
        if cost_usd == 0.0:
            top_keys = [
                k for k in output if k not in ("result", "messages", "session_id")
            ]
            logger.warning("cost=0 — JSON top-level keys: %s", top_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("failed to parse claude JSON output: %s", exc)

    # Patch the AGENT_DONE event the agent wrote with real numbers
    if storage_path:
        _patch_last_agent_done(
            storage_path, cost_usd, tokens_in, tokens_out, wall_seconds, tool_uses
        )

    return {"cost_usd": cost_usd, "session_id": session_id_out}


def handle_blocked(response: dict) -> None:
    if response.get("target_agent") == "human":
        print(
            f"\n⚠  Human checkpoint:\n{response.get('instructions', '')}\nFile: {response['file']}"
        )
    else:
        print(
            f"⚠ Blocked on {response['file']} → routed to {response.get('target_agent')}"
        )


def handle_decide(
    flow: str,
    topic: str,
    project_root: str,
    response: dict,
    interactive: bool = True,
) -> dict:
    if not interactive:
        raise RuntimeError("interactive decision required but running headless")
    print(f"\n? {response['question']}")
    for key, value in response.get("options", {}).items():
        print(f"  [{key}] {value}")
    default = response.get("default", "")
    chosen = input(f"Choice (default: {default}): ").strip()
    if not chosen or chosen not in response.get("options", {}):
        chosen = default
    return complete_stage(
        {
            "flow": flow,
            "topic": topic,
            "project_root": project_root,
            "decision": chosen,
        }
    )


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
        result = complete_stage(
            {
                "flow": flow,
                "topic": topic,
                "project_root": project_root,
                "resolved_files": resolved or None,
            }
        )
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
                print(
                    f"⚠  Feedback loop exceeded {MAX_FEEDBACK_ROUNDS} rounds on {file}. Escalating to human."
                )
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
            fb_instructions = result.get(
                "instructions", f"Resolve feedback in feedback/{file}"
            )
            invoke_agent(
                fb_instructions,
                project_root,
                model,
                state=f"resolving {file}",
                topic=topic,
                timeout=timeout,
                storage_path=storage_path,
            )
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
            response = next_action(
                {"flow": flow, "topic": topic, "project_root": project_root}
            )
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
            result = resolve_stage(
                flow,
                topic,
                project_root,
                model,
                current_state,
                timeout,
                storage_path=storage,
            )
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
    parser.add_argument(
        "--rigor", default="standard", choices=["lite", "standard", "strict"]
    )
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--project-root", default=None)
    parser.add_argument("--timeout", default=600, type=int)
    args = parser.parse_args()
    project_root = args.project_root or str(Path.cwd())
    sys.exit(
        run_flow(
            args.flow, args.topic, project_root, args.rigor, args.model, args.timeout
        )
    )
