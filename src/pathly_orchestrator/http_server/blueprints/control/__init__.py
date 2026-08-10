"""Control-plane blueprints — the unified run read + control API (unified-control-plane).

Aggregated for registration in app.py (mirrors comms/__init__.py). read side = runs_read
(GET /runs, /runs/<id>); control side = runs_control (POST /runs/<id>/stop — the run_id-addressed
stop). run_streams.py / _lifecycle.py arrive later.
"""

from .runs_control import bp as runs_control_bp
from .runs_read import bp as runs_read_bp

all_blueprints = [runs_read_bp, runs_control_bp]
