"""Smoke the base before a run's first spawn (build-proof 12).

A run that starts on a red base spends its whole budget on a failure it did not cause, and the
builder is then blamed for it. So, before the first spawn of a flow that has a ``command_gate``
on ``build`` (``team``, ``team-build``, ``goal-loop``), :func:`check_base` runs the project's
own command: the app setting ``verify.smoke``, else ``verify.build``, with neither meaning
"skip", as ``command_gate`` does when nothing is configured. Exit 0 lets the run go on. Anything
else (a non-zero exit, a timeout, a command that cannot run) parks the run with
``error_kind="base_red"`` and a human escalation, before anything was spawned.

``api.start_run`` calls it. ``api.resume_parked_run`` smokes again only after a ``base_red``
park, so work in progress on a run that stopped on a human checkpoint does not re-park it.
"""

from __future__ import annotations

import json
from typing import Callable, Optional

from pathly_orchestrator.proof.command import clip, run_command

from .human_escalation import post_human_escalation
from .registry import _lock, _set_status
from .state import RunnerState, logger


def _has_build_gate(flow_config: dict) -> bool:
    """True when some transition of the flow has a ``command_gate`` on ``build``."""
    gates = (flow_config or {}).get("gates")
    if not isinstance(gates, dict):
        return False
    return any(
        isinstance(gate, dict)
        and gate.get("type") == "command_gate"
        and gate.get("command_key") == "build"
        for entries in gates.values()
        for gate in entries or []
    )


def _smoke_command() -> Optional[tuple[str, str]]:
    """``(command, setting key)`` for ``verify.smoke``, else ``verify.build``, else None."""
    from pathly_orchestrator.fsm.gates.command import _get_setting

    for key in ("verify.smoke", "verify.build"):
        command = _get_setting(key)
        if command:
            return command, key
    return None


def _red_text(state: RunnerState, command: str, key: str, how: str, output: str) -> str:
    resume = f"POST /runner/resume-parked {json.dumps({'topic': state.topic})}"
    return (
        "The base is red: the smoke check failed before this run spawned anything.\n\n"
        f"Command (`{key}`): `{command}`\n"
        f"Directory: {state.project_root}\n"
        f"Result: {how}\n\n"
        "Nothing was spawned, so this failure is not the run's. Fix the base (or the "
        f"`verify.smoke` / `verify.build` setting), then resume this run: `{resume}`. "
        "The smoke runs again before the first spawn.\n\n"
        f"```\n{clip(output) or '(no output captured)'}\n```"
    )


def _check(state: RunnerState, broadcast_fn: Optional[Callable]) -> bool:
    from pathly_orchestrator.fsm.gates.command import _resolve_timeout
    from pathly_orchestrator.supervisor import fan_out

    if not _has_build_gate(fan_out.load_flow_config(state.flow, state.project_root)):
        return True
    found = _smoke_command()
    if found is None:
        return True
    command, key = found
    timeout = _resolve_timeout({})
    result = run_command(
        command, state.project_root, timeout, extra_env={"PATHLY_VERIFY_GATE": "1"}
    )
    if result.code == 0:
        return True

    if result.timed_out:
        how = f"timed out after {timeout}s (killed by the smoke check)"
    elif result.code is None:
        how = f"could not run ({result.error})"
    else:
        how = f"exited {result.code}"
    post_human_escalation(state, _red_text(state, command, key, how, result.output))
    with _lock:
        state.error_kind = "base_red"
        _set_status(state, "parked", broadcast_fn)
    if broadcast_fn:
        try:
            broadcast_fn(
                state.topic,
                {
                    "type": "RUNNER_PARKED",
                    "topic": state.topic,
                    "message": f"The base is red before the first spawn: {how}",
                    "kind": "base_red",
                },
            )
        except Exception as exc:
            logger.warning("broadcast_fn error: %s", exc)
    return False


def check_base(state: RunnerState, broadcast_fn: Optional[Callable]) -> bool:
    """True when the run may spawn; False when it was parked as ``base_red``.

    Fails open: if the check itself breaks (it should not), the run goes on, as a gate that
    cannot be read does.
    """
    try:
        return _check(state, broadcast_fn)
    except Exception:
        logger.warning(
            "base smoke for %s could not be evaluated; not blocking the run",
            state.topic,
            exc_info=True,
        )
        return True
