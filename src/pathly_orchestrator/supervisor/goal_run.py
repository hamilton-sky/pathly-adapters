"""Re-export shim — goal run/decompose logic is split across domain modules.

Import directly from the domain modules for new code:
  goal_executor   — start_goal_run + execution strategies (single, loop, team)
  goal_decomposer — start_goal_decompose + decomposition strategies (planner, consultation)
"""

from .goal_executor import (  # noqa: F401
    _DEFAULT_MODEL,
    _TEAM_FLOW,
    _run_loop,
    _run_single,
    _run_team,
    _safe_call,
    start_goal_run,
)
from .goal_decomposer import (  # noqa: F401
    _CONSULTATION_FLOW,
    _decompose_consultation,
    _decompose_plan,
    _decompose_planner,
    start_goal_decompose,
)
