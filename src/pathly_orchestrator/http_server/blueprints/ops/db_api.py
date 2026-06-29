"""DB API blueprint — re-exports bp after loading route sub-modules.

Routes split by concern:
  db_api_explorer.py  — stats, features, per-feature sub-resources (events/agents/otel/runs), trends
  db_api_admin.py     — sandboxed query, settings read/write
  db_api_rollup.py    — feature -> project -> global telemetry roll-up (aggregate-on-read)
"""

from ._db_api_bp import bp  # noqa: F401

# Import sub-modules to register their routes against bp.
from . import db_api_explorer as _de  # noqa: F401
from . import db_api_admin as _da  # noqa: F401
from . import db_api_rollup as _dr  # noqa: F401
