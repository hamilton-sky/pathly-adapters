"""Runner API blueprint — re-exports bp after loading route sub-modules.

Routes split by concern:
  api_lifecycle.py  — start, terminal-started, terminal-result, abort, status
  api_control.py    — pause, resume, advance, decision, agent-answer, reroute, retry, event
"""

from ._runner_bp import bp  # noqa: F401

# Import sub-modules to register their routes against bp.
from . import api_lifecycle as _al  # noqa: F401
from . import api_control as _ac  # noqa: F401
