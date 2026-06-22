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
from .blueprints.core.health import bp as health_bp
from .blueprints.core.fsm import bp as fsm_bp
from .blueprints.runner.api import bp as runner_bp
from .blueprints.runner.streams import bp as streams_bp
from .blueprints.flows.defs import bp as flow_defs_bp
from .blueprints.flows.stage_configs import bp as stage_configs_bp
from .blueprints.catalog.items import bp as catalog_bp
from .blueprints.skills.editor import bp as skills_bp
from .blueprints.comms import all_blueprints as comms_blueprints
from .blueprints.ops.telemetry import bp as telemetry_bp
from .blueprints.ops.menu import bp as menu_bp
from .blueprints.ops.db_api import bp as db_api_bp
from .blueprints.ops.chat import bp as chat_bp

app = Flask(__name__)

# Register the existing api blueprint
app.register_blueprint(api_bp)

# Register all new blueprints (no url_prefix — routes are absolute as in the original)
app.register_blueprint(health_bp)
app.register_blueprint(fsm_bp)
app.register_blueprint(runner_bp)
app.register_blueprint(telemetry_bp)
app.register_blueprint(skills_bp)
app.register_blueprint(flow_defs_bp)
app.register_blueprint(catalog_bp)
app.register_blueprint(stage_configs_bp)
app.register_blueprint(menu_bp)
app.register_blueprint(chat_bp)
app.register_blueprint(streams_bp)
app.register_blueprint(db_api_bp)
for _comms_bp in comms_blueprints:
    app.register_blueprint(_comms_bp)

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
    _middleware.configure(
        cors_origin=settings.cors_origin, api_secret=settings.api_secret
    )
    # Also keep the package-level names in sync for backward compat
    _self._RATE_LIMIT_MAX = settings.rate_limit_max
    _self._RATE_LIMIT_WINDOW = settings.rate_limit_window

    logger = logging.getLogger("pathly.http")
    logger.info("Starting pathly-fsm HTTP server on %s:%s", host, port)
    logger.info("  POST %s:%s/next_action", host, port)
    logger.info("  POST %s:%s/complete_stage", host, port)
    logger.info("  GET  %s:%s/health", host, port)
    logger.info("  GET  %s:%s/events/stream?topic=TOPIC&project_root=PATH", host, port)

    # Instantiate pipeline-level subscribers (EventBus side-effects on import).
    import pathly_orchestrator.metrics  # noqa: F401
    import pathly_orchestrator.webhook  # noqa: F401

    project_root = settings.project_root
    _watcher_stop = threading.Event()
    if project_root and flags.feedback_watcher:
        threading.Thread(
            target=_feedback_watcher, args=(project_root, _watcher_stop), daemon=True
        ).start()

    # Warm the embedding model in the background so the first POST /comms/post
    # doesn't block on the ~1-2s model load.
    from pathly_orchestrator.runner.embeddings import warm as _warm_embeddings

    threading.Thread(target=_warm_embeddings, daemon=True).start()

    # Run Flask in non-debug mode, with warnings suppressed
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
