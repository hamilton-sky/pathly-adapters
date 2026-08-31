"""Executed verification gate — ``command_gate``.

The only gate that establishes GROUND TRUTH. Every other gate reads a file an agent
wrote and trusts it; this one runs the project's own build/test/lint command, reads the
process exit code, and routes the real output back as feedback when it is non-zero.

Declaration (flow YAML)::

    gates:
      TESTING->RETRO:
        - type: command_gate
          command_key: test          # → app-setting `verify.test`
          on_fail: TEST_FAILURES.md
          timeout: 900               # optional, seconds

Command resolution, highest precedence first:

1. ``gate["command"]`` — a literal in the flow YAML (escape hatch, mostly for tests).
2. app setting ``verify.<command_key>`` — the normal path, per-project in the DB.
3. neither → the gate SKIPS (``GATE_SKIPPED`` / ``no_command_configured``).

Rule 3 is deliberate: adding this gate to a shared flow must not break a project that has
not configured a verify command. Absent config fails OPEN; a command that runs and fails —
or cannot be executed at all — fails CLOSED, because a verify command that silently does
nothing is worse than no gate.

The command is split with :func:`shlex.split` and run WITHOUT a shell, so ``&&``, ``|``
and ``>`` are not operators — wrap those in a script and call the script. A value starting
with ``[`` is parsed as a JSON argv array instead, for exact control on any platform.

Windows: without a shell, ``argv[0]`` must be a real executable, so batch-file shims
(``npm``, ``yarn``, ``tsc`` — all ``.cmd``) do not resolve by bare name. Use the JSON form
with the extension: ``["npm.cmd", "test"]``.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from pathlib import Path

from ._helpers import append_event, gate_failed, gate_skipped, project_root_of

_DEFAULT_TIMEOUT = 600
_HEAD_CHARS = 3000
_TAIL_CHARS = 5000


def _get_setting(key: str) -> str | None:
    try:
        from pathly_orchestrator.db.connection import get_db
        from pathly_orchestrator.db.queries.app_settings import get_setting

        raw = get_setting(get_db(), key, None)
    except Exception:
        return None
    return raw.strip() if isinstance(raw, str) and raw.strip() else None


def _resolve_command(gate: dict) -> tuple[str | None, str]:
    """Return (command_string_or_None, setting_key_for_diagnostics)."""
    command_key = str(gate.get("command_key") or "").strip()
    setting_key = f"verify.{command_key}" if command_key else "verify.<command_key>"
    literal = gate.get("command")
    if isinstance(literal, str) and literal.strip():
        return literal.strip(), setting_key
    if not command_key:
        return None, setting_key
    return _get_setting(setting_key), setting_key


def _resolve_timeout(gate: dict) -> int:
    for candidate in (gate.get("timeout"), _get_setting("verify.timeout_seconds")):
        try:
            value = int(candidate)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return _DEFAULT_TIMEOUT


def _to_argv(command: str) -> list[str]:
    """Split a configured command into argv. A JSON array is taken verbatim."""
    if command.startswith("["):
        parsed = json.loads(command)
        if not isinstance(parsed, list) or not parsed:
            raise ValueError("JSON command must be a non-empty array")
        return [str(part) for part in parsed]
    argv = shlex.split(command)
    if not argv:
        raise ValueError("command is empty after splitting")
    return argv


def _clip(text: str) -> str:
    """Bound the captured output, keeping BOTH ends.

    Compilers put the first error at the top; test runners put the summary at the bottom.
    Tailing alone loses the former, so keep a head and a tail with the middle elided.
    """
    text = text.strip()
    if len(text) <= _HEAD_CHARS + _TAIL_CHARS:
        return text
    elided = len(text) - _HEAD_CHARS - _TAIL_CHARS
    return f"{text[:_HEAD_CHARS]}\n\n… [{elided} characters elided] …\n\n{text[-_TAIL_CHARS:]}"


def _failure_reason(
    command: str, exit_code: int | None, output: str, detail: str
) -> str:
    code = "timed out" if exit_code is None else f"exited {exit_code}"
    body = _clip(output)
    return (
        f"Verification command failed — this is a MEASURED result, not a review opinion.\n\n"
        f"Command: `{command}`\n"
        f"Result: {code}{detail}\n\n"
        f"**Action required:** make this command exit 0, then the flow advances.\n\n"
        f"```\n{body or '(no output captured)'}\n```\n"
    )


def check_command_gate(
    gate: dict,
    storage_path: Path,
    prev_state: str,
    next_state: str,
    **_: object,
) -> dict | None:
    command, setting_key = _resolve_command(gate)
    if not command:
        gate_skipped(storage_path, "command_gate", "no_command_configured")
        return None

    try:
        argv = _to_argv(command)
    except (ValueError, json.JSONDecodeError) as exc:
        return gate_failed(
            storage_path,
            gate,
            "command_gate",
            prev_state,
            next_state,
            _failure_reason(
                command,
                None,
                "",
                f" — the configured command could not be parsed ({exc}). "
                f"Fix the `{setting_key}` setting.",
            ),
            extra={"reason": "command_unparseable", "command": command},
        )

    timeout = _resolve_timeout(gate)
    cwd = project_root_of(storage_path)
    started = time.monotonic()

    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, "PATHLY_VERIFY_GATE": "1"},
        )
    except subprocess.TimeoutExpired as exc:
        output = _decode(exc.stdout) + _decode(exc.stderr)
        return gate_failed(
            storage_path,
            gate,
            "command_gate",
            prev_state,
            next_state,
            _failure_reason(
                command, None, output, f" after {timeout}s (killed by the gate)"
            ),
            extra={"reason": "command_timeout", "command": command},
        )
    except (OSError, ValueError) as exc:
        # Not-found / not-executable is a CONFIG error, and it fails closed on purpose:
        # a verify command that never runs would silently pass every gate forever.
        return gate_failed(
            storage_path,
            gate,
            "command_gate",
            prev_state,
            next_state,
            _failure_reason(
                command,
                None,
                "",
                f" — the command could not be executed ({exc}). "
                f"Check the `{setting_key}` setting and that the tool is installed.",
            ),
            extra={"reason": "command_not_executable", "command": command},
        )

    duration_ms = int((time.monotonic() - started) * 1000)
    output = (completed.stdout or "") + (completed.stderr or "")

    if completed.returncode == 0:
        append_event(
            storage_path,
            {
                "type": "GATE_PASSED",
                "gate": "command_gate",
                "transition": f"{prev_state}->{next_state}",
                "command": command,
                "exit_code": 0,
                "duration_ms": duration_ms,
            },
        )
        return None

    return gate_failed(
        storage_path,
        gate,
        "command_gate",
        prev_state,
        next_state,
        _failure_reason(command, completed.returncode, output, ""),
        extra={
            "reason": f"`{command}` exited {completed.returncode}",
            "command": command,
            "exit_code": completed.returncode,
            "duration_ms": duration_ms,
        },
    )


def _decode(raw: object) -> str:
    if isinstance(raw, bytes):
        return raw.decode("utf-8", "replace")
    return raw if isinstance(raw, str) else ""
