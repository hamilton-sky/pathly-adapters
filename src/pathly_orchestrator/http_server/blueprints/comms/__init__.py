"""Comms board blueprints — aggregated for registration in app.py."""

from .messages import bp as messages_bp
from .tasks import bp as tasks_bp
from .artifacts import bp as artifacts_bp
from .runs import bp as runs_bp
from .goals import bp as goals_bp
from .settings import bp as settings_bp
from .context import bp as context_bp

# Back-compat re-exports: these internal symbols moved into _helpers when this
# blueprint was decomposed into a subpackage. Re-export them at the package level
# so existing importers (and the write-perm / embed-curation test suites) keep
# working against the historical `blueprints.comms` import path.
from ._helpers import (  # noqa: F401
    _EMBED_TYPES,
    _GLOBAL_WRITERS,
    _PROJECT_WRITERS,
    check_write_permission as _check_write_permission,
)

all_blueprints = [
    messages_bp,
    tasks_bp,
    artifacts_bp,
    runs_bp,
    goals_bp,
    settings_bp,
    context_bp,
]
