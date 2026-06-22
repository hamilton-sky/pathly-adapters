"""Comms board blueprints — aggregated for registration in app.py."""

from .messages import bp as messages_bp
from .tasks import bp as tasks_bp
from .artifacts import bp as artifacts_bp
from .runs import bp as runs_bp
from .goals import bp as goals_bp
from .settings import bp as settings_bp

all_blueprints = [
    messages_bp,
    tasks_bp,
    artifacts_bp,
    runs_bp,
    goals_bp,
    settings_bp,
]
