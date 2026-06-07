"""runner package — public surface re-exported for backward compatibility."""

from pathly_orchestrator.fsm_http_client import next_action, complete_stage

from .argv import _storage_path, resolve_argv, resolve_interactive_argv
from .output import _extract_json_payload, parse_result
from .events import _patch_last_agent_done, read_last_agent_done, tail_agent_done
from .history import build_pipeline_history_block
from .invoke import invoke_agent
from .cli import handle_blocked, handle_decide, resolve_stage, run_flow, main

__all__ = [
    "_storage_path",
    "resolve_argv",
    "resolve_interactive_argv",
    "_extract_json_payload",
    "parse_result",
    "_patch_last_agent_done",
    "read_last_agent_done",
    "tail_agent_done",
    "build_pipeline_history_block",
    "invoke_agent",
    "handle_blocked",
    "handle_decide",
    "resolve_stage",
    "run_flow",
    "main",
]
