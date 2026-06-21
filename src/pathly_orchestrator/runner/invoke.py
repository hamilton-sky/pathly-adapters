"""Agent subprocess invocation."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .argv import resolve_argv
from .output import parse_result
from .events import _patch_last_agent_done

logger = logging.getLogger("pathly.runner")


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
    abort_callback: Callable[[], bool] | None = None,
    proc_callback: Callable[[Any], None] | None = None,
) -> dict[str, Any]:
    """Invoke an adapter subprocess and return {cost_usd, session_id}.

    _abort_ref: deprecated; kept for backward compat. Prefer abort_callback/proc_callback.
    abort_callback: called with no args; returns True if the run should be aborted.
    proc_callback: called with the Popen object once started (for abort support).
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

    if proc_callback is not None:
        proc_callback(proc)
    elif _abort_ref is not None:
        # backward compat: store proc on _abort_ref under its own lock if available
        try:
            _abort_ref._proc = proc
        except Exception:
            pass

    stdout_bytes: bytes = b""
    try:
        use_abort = abort_callback is not None or _abort_ref is not None
        if use_abort:
            while True:
                try:
                    stdout_bytes, _ = proc.communicate(timeout=0.5)
                    break
                except subprocess.TimeoutExpired:
                    abort_now = False
                    if abort_callback is not None:
                        abort_now = abort_callback()
                    elif _abort_ref is not None:
                        try:
                            abort_now = _abort_ref._abort_flag
                        except Exception:
                            pass
                    if abort_now:
                        proc.kill()
                        if proc_callback is None and _abort_ref is not None:
                            try:
                                _abort_ref._proc = None
                            except Exception:
                                pass
                        raise RuntimeError("aborted")
                    if time.monotonic() - t_start > timeout:
                        proc.kill()
                        raise RuntimeError(
                            f"Claude subprocess timed out after {timeout}s"
                        )
        else:
            try:
                stdout_bytes, _ = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                raise RuntimeError(f"Claude subprocess timed out after {timeout}s")
    finally:
        if proc_callback is None and _abort_ref is not None:
            try:
                _abort_ref._proc = None
            except Exception:
                pass

    wall_seconds = int(time.monotonic() - t_start)

    if proc.returncode != 0:
        raise RuntimeError(f"Claude subprocess exited with code {proc.returncode}")

    cost_usd = 0.0
    tokens_in = 0
    tokens_out = 0
    tool_uses = 0
    session_id_out: str | None = None
    try:
        raw_text = stdout_bytes.decode("utf-8", errors="replace")
        parsed = parse_result(adapter, raw_text)
        cost_usd = float(parsed.get("cost_usd", 0.0) or 0.0)
        session_id_out = parsed.get("session_id") or None
        tokens_in = parsed.get("tokens_in", 0)
        tokens_out = parsed.get("tokens_out", 0)
        tool_uses = parsed.get("tool_uses", 0)
        result_text = parsed.get("result", "")
        if result_text:
            print(result_text)
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
            logger.warning(
                "cost=0 from PTY stdout — billing will arrive via BILLING_UPDATE"
            )
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("failed to parse claude JSON output: %s", exc)

    if storage_path:
        _patch_last_agent_done(
            storage_path, cost_usd, tokens_in, tokens_out, wall_seconds, tool_uses
        )

    return {"cost_usd": cost_usd, "session_id": session_id_out}
