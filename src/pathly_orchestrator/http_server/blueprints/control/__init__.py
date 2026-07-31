"""Control-plane blueprints — the unified run read API (unified-control-plane P0).

Aggregated for registration in app.py (mirrors comms/__init__.py). P0 exposes only the
read side (runs_read); runs_control.py / run_streams.py / _lifecycle.py arrive in P1-P3.
"""

from .runs_read import bp as runs_read_bp

all_blueprints = [runs_read_bp]
