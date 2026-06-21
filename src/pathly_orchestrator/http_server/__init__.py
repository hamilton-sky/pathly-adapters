"""HTTP wrapper for the pathly FSM.

Provides REST endpoints for FSM operations.

Run: python -m pathly_orchestrator.http_server
Or: pathly-fsm-http

Environment variables:
  PATHLY_FSM_HTTP_PORT: Port to listen on (default 8765)
  PATHLY_FSM_HTTP_HOST: Host to bind to (default 127.0.0.1)
  PATHLY_PROJECT_ROOT: If set, enables feedback file watcher on that project root
"""

from __future__ import annotations

# Re-export the Flask app and main entry point
from .app import app, main

# Re-export middleware symbols that tests access directly
from .middleware import (
    _rate_counters,
    _RATE_LIMIT_MAX,
    _RATE_LIMIT_WINDOW,
    _rate_lock,
    _metrics,
    _metrics_lock,
    _inc,
    _check_rate_limit,
    _JsonFormatter,
    _setup_logging,
    logger,
)

# Re-export SSE globals that tests access directly
from .sse import (
    _NO_FEATURE_MENU,
    _clients,
    _lock,
    _tailers,
    _menu_clients,
    _menu_lock,
    _runner_clients,
    _runner_lock,
    _push_timer,
    _push_timer_lock,
    _broadcast,
    _broadcast_sse,
    _broadcast_runner,
    _tail_events,
    _push_menu_to_sse,
    _fire_push_clear,
    _schedule_push_clear,
)

# Re-export feedback symbols
from .feedback import (
    _ARCH_QUESTION,
    _FENCE,
    _TTL_KEY,
    _TTL_LINE,
    _classify_content,
    _has_ttl,
    _inject_ttl,
    _process_feedback_file,
    _feedback_watcher,
)

# Re-export pricing symbols
from .pricing import compute_cost_usd
from .telemetry_registry import PricingRegistry

# Re-export FSM functions that tests patch via this module's namespace
from pathly_orchestrator.fsm_ops import next_action, complete_stage

__all__ = [
    "app",
    "main",
    # middleware
    "_rate_counters",
    "_RATE_LIMIT_MAX",
    "_RATE_LIMIT_WINDOW",
    "_rate_lock",
    "_metrics",
    "_metrics_lock",
    "_inc",
    "_check_rate_limit",
    "_JsonFormatter",
    "_setup_logging",
    "logger",
    # sse
    "_NO_FEATURE_MENU",
    "_clients",
    "_lock",
    "_tailers",
    "_menu_clients",
    "_menu_lock",
    "_runner_clients",
    "_runner_lock",
    "_push_timer",
    "_push_timer_lock",
    "_broadcast",
    "_broadcast_sse",
    "_broadcast_runner",
    "_tail_events",
    "_push_menu_to_sse",
    "_fire_push_clear",
    "_schedule_push_clear",
    # feedback
    "_ARCH_QUESTION",
    "_FENCE",
    "_TTL_KEY",
    "_TTL_LINE",
    "_classify_content",
    "_has_ttl",
    "_inject_ttl",
    "_process_feedback_file",
    "_feedback_watcher",
    # pricing
    "compute_cost_usd",
    "PricingRegistry",
    # fsm
    "next_action",
    "complete_stage",
]
