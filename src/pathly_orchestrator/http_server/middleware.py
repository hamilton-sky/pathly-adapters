"""Logging, rate limiting, and metrics middleware."""
from __future__ import annotations

import collections
import json
import logging
import sys
import threading
import time
import uuid

from pathly_orchestrator.feature_flags import flags

logger = logging.getLogger("pathly.http")

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 120  # requests per window per IP

# Configurable at startup by app.main() via configure()
_cors_origin: str = "*"
_api_secret: str = ""


def configure(cors_origin: str, api_secret: str) -> None:
    """Apply runtime settings — called once by app.main() after Settings.from_env()."""
    global _cors_origin, _api_secret
    _cors_origin = cors_origin
    _api_secret = api_secret
_rate_counters: dict[str, collections.deque] = {}
_rate_lock = threading.Lock()

# Prometheus-format metrics
_metrics: dict[str, int | float] = {
    "pathly_requests_total": 0,
    "pathly_requests_rate_limited_total": 0,
    "pathly_request_errors_total": 0,
    "pathly_sse_clients_active": 0,
}
_metrics_lock = threading.Lock()


# The standard attributes present on every LogRecord instance — used to keep
# only genuine `extra=` fields. The previous check used LogRecord.__dict__ (the
# CLASS dict), which does NOT contain instance attributes like `args`, so they
# all leaked into the JSON. A third party logging a non-serializable arg (e.g.
# an httpx URL object) then crashed json.dumps on every request.
_STD_LOGRECORD_ATTRS = set(
    logging.LogRecord("", logging.INFO, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        extra = {
            k: v
            for k, v in record.__dict__.items()
            if k not in _STD_LOGRECORD_ATTRS and not k.startswith("_")
        }
        log.update(extra)
        # default=str: never let a stray non-serializable value crash logging.
        return json.dumps(log, default=str)


def _setup_logging() -> None:
    """Configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _inc(key: str, amount: int | float = 1) -> None:
    with _metrics_lock:
        _metrics[key] = _metrics.get(key, 0) + amount


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate limited."""
    import sys
    # Tests override _RATE_LIMIT_MAX on the package module (http_server.__init__);
    # read the effective value from there if available, otherwise use this module's value.
    _pkg = sys.modules.get("pathly_orchestrator.http_server")
    max_val = getattr(_pkg, "_RATE_LIMIT_MAX", _RATE_LIMIT_MAX) if _pkg is not None else _RATE_LIMIT_MAX
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    with _rate_lock:
        dq = _rate_counters.setdefault(ip, collections.deque())
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= max_val:
            return False
        dq.append(now)
        return True


def _log_request():
    from flask import request, jsonify
    # Health endpoint bypasses all middleware — must respond before rate-limiting.
    if request.path == "/health":
        return None

    # Handle CORS preflight (OPTIONS) before any routing or rate limiting.
    # The browser sends this before every cross-origin POST with Content-Type: application/json.
    if request.method == "OPTIONS":
        from flask import Response as _Resp
        resp = _Resp()
        if _cors_origin:
            resp.headers["Access-Control-Allow-Origin"] = _cors_origin
            resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pathly-Secret"
            resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

    # Auth check — skip for health (already exited above) and read-only SSE streams
    if _api_secret and not request.path.startswith("/events/"):
        token = request.headers.get("X-Pathly-Secret") or request.args.get("token", "")
        if token != _api_secret:
            from flask import jsonify as _jsonify
            return _jsonify({"error": "unauthorized"}), 401

    if flags.rate_limiting and not _check_rate_limit(request.remote_addr or "unknown"):
        _inc("pathly_requests_rate_limited_total")
        return jsonify({"error": "Rate limit exceeded"}), 429
    _inc("pathly_requests_total")
    request_id = str(uuid.uuid4())[:8]
    request.environ["REQUEST_ID"] = request_id
    logger.info(
        "request",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.path,
            "remote": request.remote_addr,
        },
    )


def _log_response(response):
    from flask import request
    request_id = request.environ.get("REQUEST_ID", "")
    logger.info(
        "response", extra={"request_id": request_id, "status": response.status_code}
    )
    if response.status_code >= 500:
        _inc("pathly_request_errors_total")
    if _cors_origin:
        response.headers["Access-Control-Allow-Origin"] = _cors_origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Pathly-Secret"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response
