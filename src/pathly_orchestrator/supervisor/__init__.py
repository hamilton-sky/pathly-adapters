"""Supervisor package: re-exports all public and private symbols for backward compatibility."""

from .state import RunnerState, OpenSession, VALID_STATUSES, MAX_FEEDBACK_ROUNDS, logger
from .registry import (
    _registry,
    _lock,
    _TERMINAL_RESULT_TIMEOUT,
    TerminalRun,
    create_run,
    get_run,
    drop_run,
    get_state,
    recover_stale_mirrors,
    _write_mirror,
    _set_status,
    _cleanup_run_id,
)
from .terminal import _run_stage_via_terminal, _agent_done_watcher, _reconciliation_window, _write_supervisor_phase_summary
from .interactions import _await_agent_question
from .orchestrator import _loop, _resolve_stage_supervised
from .api import start_run, pause_run, resume_run, abort_run, supply_decision, supply_agent_answer, reroute_run

__all__ = [
    "RunnerState",
    "OpenSession",
    "VALID_STATUSES",
    "MAX_FEEDBACK_ROUNDS",
    "logger",
    "_registry",
    "_lock",
    "_TERMINAL_RESULT_TIMEOUT",
    "TerminalRun",
    "create_run",
    "get_run",
    "drop_run",
    "get_state",
    "recover_stale_mirrors",
    "_write_mirror",
    "_set_status",
    "_cleanup_run_id",
    "_run_stage_via_terminal",
    "_agent_done_watcher",
    "_reconciliation_window",
    "_write_supervisor_phase_summary",
    "_await_agent_question",
    "_loop",
    "_resolve_stage_supervised",
    "start_run",
    "pause_run",
    "resume_run",
    "abort_run",
    "supply_decision",
    "supply_agent_answer",
    "reroute_run",
]
