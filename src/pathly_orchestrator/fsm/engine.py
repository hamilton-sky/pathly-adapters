"""Re-export shim — FSM engine is split across domain modules.

Import directly from the domain modules for new code:
  engine_recover     — _DEFAULT_LIMITS, recover_state
  engine_transitions — evaluate_transition_rules, route_feedback, escalation helpers
  engine_actions     — run_transition_actions, run_gates, write_state, append_event
"""

from .engine_recover import _DEFAULT_LIMITS, recover_state  # noqa: F401
from .engine_transitions import (  # noqa: F401
    _ESCALATE_AT_ATTEMPT,
    _normalize_tiers,
    _read_retry_counts,
    _resolve_feedback_target,
    evaluate_transition_rules,
    route_feedback,
)
from .engine_actions import (  # noqa: F401
    _auto_commit_enabled,
    _post_commit_skipped_note,
    _scope_clean,
    _verify_passed,
    _write_gate_feedback,
    append_event,
    run_gates,
    run_transition_actions,
    write_state,
)
