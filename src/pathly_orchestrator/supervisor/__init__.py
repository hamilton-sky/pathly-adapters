"""Supervisor package: re-exports all public and private symbols for backward compatibility."""

from .state import RunnerState, OpenSession, VALID_STATUSES, MAX_FEEDBACK_ROUNDS, logger
from .registry import (
    _registry,
    _lock,
    _terminal_started_events,
    _terminal_result_events,
    _terminal_result_data,
    _agent_done_events,
    _agent_done_stop_events,
    _TERMINAL_RESULT_TIMEOUT,
    get_state,
    recover_stale_mirrors,
    _write_mirror,
    _set_status,
    _cleanup_run_id,
)
from .terminal import _run_stage_via_terminal, _agent_done_watcher, _reconciliation_window
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
    "_terminal_started_events",
    "_terminal_result_events",
    "_terminal_result_data",
    "_agent_done_events",
    "_agent_done_stop_events",
    "_TERMINAL_RESULT_TIMEOUT",
    "get_state",
    "recover_stale_mirrors",
    "_write_mirror",
    "_set_status",
    "_cleanup_run_id",
    "_run_stage_via_terminal",
    "_agent_done_watcher",
    "_reconciliation_window",
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
