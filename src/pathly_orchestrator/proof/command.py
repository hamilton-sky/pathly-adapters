"""Run one command the way Pathly runs every verify command: no shell, a timeout, clipped output.

Extracted from ``fsm/gates/command.py`` so ``command_gate`` and task check blocks share one
runner. The command is split with :func:`shlex.split` and run WITHOUT a shell, so ``&&``,
``|`` and ``>`` are not operators. A value starting with ``[`` is parsed as a JSON argv array.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

_HEAD_CHARS = 3000
_TAIL_CHARS = 5000
_CLIPPED = "\n... (clipped) ...\n"


@dataclass(frozen=True)
class CommandResult:
    """``code`` is None when the command timed out or could not run (then ``error`` says why)."""

    code: int | None
    output: str
    timed_out: bool
    error: str | None


def to_argv(command: str | list[str]) -> list[str]:
    """Split a configured command into argv. A JSON array (or a list) is taken verbatim."""
    if isinstance(command, list):
        if not command:
            raise ValueError("command list is empty")
        return [str(part) for part in command]
    if command.startswith("["):
        parsed = json.loads(command)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("JSON command must be a non-empty array")
        return [str(part) for part in parsed]
    argv = shlex.split(command)
    if not argv:
        raise ValueError("command is empty after splitting")
    return argv


def clip(text: str) -> str:
    """Bound the captured output, keeping BOTH ends.

    Compilers put the first error at the top; test runners put the summary at the bottom.
    Tailing alone loses the former, so keep a head and a tail with the middle elided.
    """
    text = text.strip()
    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return text
    elided = len(text) - _HEAD_CHARS - _TAIL_CHARS
    return f"{text[:_HEAD_CHARS]}\n\n… [{elided} characters elided] …\n\n{text[-_TAIL_CHARS:]}"


def clip_to(text: str, limit: int) -> str:
    """Head and tail of ``text`` in ``limit`` characters (a command's summary is at its end)."""
    if len(text) <= limit:
        return text
    room = max(limit - len(_CLIPPED), 0)
    head = room // 3
    tail = room - head
    return text[:head] + _CLIPPED + (text[len(text) - tail :] if tail else "")


def run_command(
    command: str | list[str],
    cwd: str | Path,
    timeout: float,
    extra_env: dict[str, str] | None = None,
) -> CommandResult:
    """Run *command* in *cwd* and return its exit code and stdout+stderr. Never raises."""
    try:
        argv = to_argv(command)
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(extra_env or {})},
        )
    except subprocess.TimeoutExpired as exc:
        output = _decode(exc.stdout) + _decode(exc.stderr)
        return CommandResult(code=None, output=output, timed_out=True, error=None)
    except (OSError, ValueError) as exc:
        return CommandResult(code=None, output="", timed_out=False, error=str(exc))
    output = (completed.stdout or "") + (completed.stderr or "")
    return CommandResult(
        code=completed.returncode, output=output, timed_out=False, error=None
    )


def _decode(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw if isinstance(raw, str) else ""
