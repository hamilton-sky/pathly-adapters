"""Flask application factory and main entry point."""
from __future__ import annotations

import sys
import threading

try:
    from flask import Flask
except ImportError:
    print(
        "Error: Flask not installed. Install with: pip install flask", file=sys.stderr
    )
    sys.exit(1)

from pathly_orchestrator.api import api_bp
from .middleware import _log_request, _log_response, _setup_logging
from .feedback import _feedback_watcher
from .blueprints.health import bp as health_bp
from .blueprints.fsm import bp as fsm_bp
from .blueprints.runner import bp as runner_bp
from .blueprints.telemetry import bp as telemetry_bp
from .blueprints.skills import bp as skills_bp
from .blueprints.menu import bp as menu_bp
from .blueprints.chat import bp as chat_bp
from .blueprints.streams import bp as streams_bp
from .blueprints import flows as _flows_bp

app = Flask(__name__)

# Register the existing api blueprint
app.register_blueprint(api_bp)

# Register all new blueprints (no url_prefix — routes are absolute as in the original)
app.register_blueprint(health_bp)
app.register_blueprint(fsm_bp)
app.register_blueprint(runner_bp)
app.register_blueprint(telemetry_bp)
app.register_blueprint(skills_bp)
app.register_blueprint(menu_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(streams_bp)
app.register_blueprint(_flows_bp.bp)

# Register request/response hooks
app.before_request(_log_request)
app.after_request(_log_response)


def main() -> None:
    """Start the HTTP server."""
    _setup_logging()

    from pathly_orchestrator.config import Settings
    from pathly_orchestrator.feature_flags import flags
    import pathly_orchestrator.http_server as _self
    import logging

    settings = Settings.from_env()
    port = settings.port
    host = settings.host

    # Update the middleware module globals (where the values actually live)
    from pathly_orchestrator.http_server import middleware as _middleware
    _middleware._RATE_LIMIT_MAX = settings.rate_limit_max
    _middleware._RATE_LIMIT_WINDOW = settings.rate_limit_window
    # Also keep the package-level names in sync for backward compat
    _self._RATE_LIMIT_MAX = settings.rate_limit_max
    _self._RATE_LIMIT_WINDOW = settings.rate_limit_window

    logger = logging.getLogger("pathly.http")
    logger.info("Starting pathly-fsm HTTP server on %s:%s", host, port)
    logger.info("  POST %s:%s/next_action", host, port)
    logger.info("  POST %s:%s/complete_stage", host, port)
    logger.info("  GET  %s:%s/health", host, port)
    logger.info("  GET  %s:%s/events/stream?topic=TOPIC&project_root=PATH", host, port)

    project_root = settings.project_root
    _watcher_stop = threading.Event()
    if project_root and flags.feedback_watcher:
        threading.Thread(
            target=_feedback_watcher, args=(project_root, _watcher_stop), daemon=True
        ).start()

    # Run Flask in non-debug mode, with warnings suppressed
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
