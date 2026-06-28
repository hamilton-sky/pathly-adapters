"""Shim — re-exports from fsm_http_client + fsm_cli for backward compat."""

from pathly_orchestrator.fsm_http_client import *  # noqa: F401, F403
from pathly_orchestrator.fsm_http_client import (  # noqa: F401
    DEFAULT_HOST,
    DEFAULT_PORT,
    _SERVER_MODULE,
    _HEALTH_PATH,
    _NEXT_ACTION_PATH,
    _COMPLETE_STAGE_PATH,
    _RECORD_ACTIVITY_PATH,
    _RECORD_PHASE_PATH,
    next_action,
    complete_stage,
    record_activity,
    record_phase,
    ensure_server_running,
    _base_url,
    _request_raw,
    _request_json,
    _health_ok,
    _pid_file,
    _start_server,
    _filter_none,
)
from pathly_orchestrator.fsm_cli import (  # noqa: F401
    _add_common_net_args,
    _main_next_action,
    _main_complete_stage,
    _main_record_activity,
    _main_record_phase,
    main,
)
