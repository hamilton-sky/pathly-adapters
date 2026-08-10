"""Control-plane blueprints — the unified run read + control API (unified-control-plane).

Aggregated for registration in app.py (mirrors comms/__init__.py). read side = runs_read
(GET /runs, /runs/<id>); control side = runs_control (POST /runs/<id>/stop — the run_id-addressed
stop); stream side = run_streams (GET /events/runs?run_id= — the unified per-run SSE feed, T3).
_lifecycle.py arrives later.
"""

from .run_streams import bp as run_streams_bp
from .runs_control import bp as runs_control_bp
from .runs_read import bp as runs_read_bp

all_blueprints = [runs_read_bp, runs_control_bp, run_streams_bp]
