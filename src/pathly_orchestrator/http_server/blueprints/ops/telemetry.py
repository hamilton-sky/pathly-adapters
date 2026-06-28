"""Telemetry blueprint — re-exports bp after loading route sub-modules.

Routes split by concern:
  telemetry_activity.py  — /record_activity
  telemetry_phase.py     — /telemetry/trends, /telemetry/pricing, /record_phase, /record_phase_summary
"""

from ._telemetry_bp import bp  # noqa: F401

# Import sub-modules to register their routes against bp.
from . import telemetry_activity as _ta  # noqa: F401
from . import telemetry_phase as _tp  # noqa: F401
