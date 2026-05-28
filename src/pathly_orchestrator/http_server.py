"""HTTP wrapper for the pathly FSM.

Provides REST endpoints for FSM operations.

Run: python -m pathly_orchestrator.http_server
Or: pathly-fsm-http

Environment variables:
  PATHLY_FSM_HTTP_PORT: Port to listen on (default 8765)
  PATHLY_FSM_HTTP_HOST: Host to bind to (default 127.0.0.1)
  PATHLY_PROJECT_ROOT: If set, enables feedback file watcher on that project root
"""

from __future__ import annotations

import collections
import json
import logging
import os
import queue
import re
import sys
import threading
import time
import uuid
from pathlib import Path

try:
    from flask import Flask, request, jsonify
except ImportError:
    print(
        "Error: Flask not installed. Install with: pip install flask", file=sys.stderr
    )
    sys.exit(1)

from pathly_orchestrator.config import Settings
from pathly_orchestrator.eventlog import read_state
from pathly_orchestrator.feature_flags import flags
from pathly_orchestrator.fsm_ops import build_menu_payload, next_action, complete_stage
from pathly_orchestrator.chat_agent import handle_chat
from pathly_telemetry.storage import append_activity

_NO_FEATURE_MENU = {
    "state": "no-feature",
    "feature": "",
    "agent": "director",
    "title": "Pathly · No active feature",
    "subtitle": "Start a new feature or explore the codebase.",
    "items": [
        {"label": "Start a new feature", "description": "Describe it and let the director route.", "command": "/pathly go", "terminal_kind": "claude"},
        {"label": "Brainstorm an idea", "description": "Open an architect storm session.", "command": "/pathly storm", "terminal_kind": "claude"},
        {"label": "Import a PRD file", "description": "Import requirements from a PRD or BMAD file.", "command": "/pathly prd-import", "terminal_kind": "claude"},
        {"label": "Explore the codebase", "description": "Read-only Q&A about the project.", "command": "/pathly explore", "terminal_kind": "claude"},
    ],
    "empty_message": "No menu items available.",
}


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
            if k not in logging.LogRecord.__dict__ and not k.startswith("_")
        }
        log.update(extra)
        return json.dumps(log)


def _setup_logging() -> None:
    """Configure structured JSON logging."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)


logger = logging.getLogger("pathly.http")

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 120  # requests per window per IP
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


def _inc(key: str, amount: int | float = 1) -> None:
    with _metrics_lock:
        _metrics[key] = _metrics.get(key, 0) + amount


def _check_rate_limit(ip: str) -> bool:
    """Return True if the request is allowed, False if rate limited."""
    now = time.time()
    cutoff = now - _RATE_LIMIT_WINDOW
    with _rate_lock:
        dq = _rate_counters.setdefault(ip, collections.deque())
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= _RATE_LIMIT_MAX:
            return False
        dq.append(now)
        return True


app = Flask(__name__)


@app.before_request
def _log_request():
    # Handle CORS preflight (OPTIONS) before any routing or rate limiting.
    # The browser sends this before every cross-origin POST with Content-Type: application/json.
    if request.method == "OPTIONS":
        from flask import Response as _Resp
        resp = _Resp()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        return resp

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


@app.after_request
def _log_response(response):
    request_id = request.environ.get("REQUEST_ID", "")
    logger.info(
        "response", extra={"request_id": request_id, "status": response.status_code}
    )
    if response.status_code >= 500:
        _inc("pathly_request_errors_total")
    # Allow renderer (Vite dev server at localhost:5173 or Electron) to call the API
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


# SSE client registry: (topic, project_root) -> list of subscriber queues
_clients: dict[tuple[str, str], list[queue.Queue]] = {}
_lock = threading.Lock()
_tailers: dict[tuple[str, str], threading.Event] = {}


def _broadcast(key: tuple[str, str], line: str) -> None:
    with _lock:
        for q in _clients.get(key, []):
            try:
                q.put_nowait(line)
            except queue.Full:
                pass


def _tail_events(key: tuple[str, str], stop: threading.Event) -> None:
    topic, project_root = key
    path = Path(project_root) / "pathly" / "plans" / topic / "EVENTS.jsonl"
    pos = path.stat().st_size if path.exists() else 0
    while not stop.is_set():
        try:
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    f.seek(pos)
                    for raw in f:
                        raw = raw.strip()
                        if raw:
                            _broadcast(key, raw)
                    pos = f.tell()
        except Exception:
            logger.debug("tail_events error", exc_info=True)
        stop.wait(0.1)


@app.route("/health", methods=["GET"])
def health():
    """Deep health check."""
    checks: dict[str, object] = {
        "status": "ok",
        "server": "pathly-fsm-http",
        "sse_clients": _metrics.get("pathly_sse_clients_active", 0),
    }
    project_root = os.environ.get("PATHLY_PROJECT_ROOT", "")
    if project_root:
        from pathlib import Path

        root = Path(project_root)
        checks["project_root_exists"] = root.exists()
        checks["project_root_writable"] = os.access(project_root, os.W_OK)
    return jsonify(checks), 200


@app.route("/status", methods=["GET"])
def status_endpoint():
    """Read-only FSM state endpoint for the Studio renderer.

    Query params:
      project_root (optional): absolute path to project root;
                               falls back to PATHLY_PROJECT_ROOT env var.

    Returns JSON:
      { "current_state": str, "feature": str, "project_root": str }
    or { "current_state": "unknown" } if STATE.json not found or project_root not set.
    """
    project_root = request.args.get("project_root", "").strip()
    if not project_root:
        project_root = os.environ.get("PATHLY_PROJECT_ROOT", "").strip()

    if not project_root:
        return jsonify({"current_state": "unknown"}), 200

    resolved_root = Path(project_root).resolve()
    plans_dir = resolved_root / "pathly" / "plans"
    if not plans_dir.resolve().is_relative_to(resolved_root):
        return jsonify({"error": "Invalid project_root"}), 400
    if not plans_dir.exists():
        return jsonify({"current_state": "no-feature", "feature": "", "project_root": project_root, "menu": _NO_FEATURE_MENU}), 200

    # Find the most recently updated STATE.json across all features.
    best_state: dict | None = None
    best_mtime: float = -1.0
    try:
        for state_file in plans_dir.glob("*/STATE.json"):
            if not state_file.resolve().is_relative_to(resolved_root):
                continue
            try:
                mtime = state_file.stat().st_mtime
                if mtime > best_mtime:
                    candidate = read_state(str(state_file.parent))
                    if candidate is not None:
                        best_mtime = mtime
                        best_state = candidate
            except Exception:
                logger.debug("status: error reading %s", state_file, exc_info=True)
    except Exception:
        logger.debug("status: error scanning plans dir", exc_info=True)
        return jsonify({"current_state": "unknown"}), 200

    if best_state is None:
        return jsonify({"current_state": "no-feature", "feature": "", "project_root": project_root, "menu": _NO_FEATURE_MENU}), 200

    menu = None
    try:
        from importlib.resources import files
        import yaml

        flow_config = yaml.safe_load(
            files("pathly_data").joinpath("core/flows/team.flow.yaml").read_text(encoding="utf-8")
        )
        feature = best_state.get("feature", "")
        storage_path = resolved_root / "pathly" / "plans" / feature
        menu = build_menu_payload(
            flow_config,
            best_state.get("current", "unknown"),
            storage_path,
        )
    except Exception:
        logger.debug("status: error building menu payload", exc_info=True)

    return jsonify(
        {
            "current_state": best_state.get("current", "unknown"),
            "feature": best_state.get("feature", ""),
            "project_root": project_root,
            "menu": menu,
        }
    ), 200


@app.route("/metrics", methods=["GET"])
def metrics_endpoint():
    """Prometheus text-format metrics endpoint."""
    from flask import Response

    with _metrics_lock:
        snapshot = dict(_metrics)
    lines = [
        "# HELP pathly_requests_total Total HTTP requests received",
        "# TYPE pathly_requests_total counter",
        f"pathly_requests_total {snapshot.get('pathly_requests_total', 0)}",
        "# HELP pathly_requests_rate_limited_total Requests rejected by rate limiter",
        "# TYPE pathly_requests_rate_limited_total counter",
        f"pathly_requests_rate_limited_total {snapshot.get('pathly_requests_rate_limited_total', 0)}",
        "# HELP pathly_request_errors_total HTTP 5xx responses",
        "# TYPE pathly_request_errors_total counter",
        f"pathly_request_errors_total {snapshot.get('pathly_request_errors_total', 0)}",
        "# HELP pathly_sse_clients_active Currently connected SSE clients",
        "# TYPE pathly_sse_clients_active gauge",
        f"pathly_sse_clients_active {snapshot.get('pathly_sse_clients_active', 0)}",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain; version=0.0.4")


_ARCH_QUESTION = re.compile(
    r"\b(architect|architecture|architectural|design|approach|structure)\b",
    re.IGNORECASE,
)
_TTL_KEY = "ttl_hours"
_TTL_LINE = "ttl_hours: 48"
_FENCE = "---"


def _classify_content(content: str) -> str:
    lines = content.splitlines()
    tagged = []
    for line in lines:
        stripped = line.strip()
        if (
            stripped.startswith("- ")
            and not stripped.startswith("- [REQ]")
            and not stripped.startswith("- [ARCH]")
        ):
            question_text = stripped[2:]
            if _ARCH_QUESTION.search(question_text):
                tagged.append(f"- [ARCH] {stripped[2:]}")
            else:
                tagged.append(f"- [REQ] {stripped[2:]}")
        else:
            tagged.append(line)
    return "\n".join(tagged) + "\n"


def _has_ttl(content: str) -> bool:
    lines = content.splitlines()
    in_frontmatter = False
    for i, line in enumerate(lines):
        if i == 0 and line.strip() == _FENCE:
            in_frontmatter = True
            continue
        if in_frontmatter:
            if line.strip() == _FENCE:
                break
            if line.startswith(_TTL_KEY + ":"):
                return True
    return False


def _inject_ttl(content: str) -> str:
    lines = content.splitlines()
    if lines and lines[0].strip() == _FENCE:
        return _FENCE + "\n" + _TTL_LINE + "\n" + "\n".join(lines[1:]) + "\n"
    return _FENCE + "\n" + _TTL_LINE + "\n" + _FENCE + "\n" + content


def _process_feedback_file(path: Path) -> None:
    try:
        content = path.read_text(encoding="utf-8")
        if not _has_ttl(content):
            content = _inject_ttl(content)
        content = _classify_content(content)
        path.write_text(content, encoding="utf-8")
    except OSError:
        logger.warning("feedback file write failed: %s", path, exc_info=True)


def _feedback_watcher(project_root: str, stop: threading.Event) -> None:
    plans_dir = Path(project_root) / "pathly" / "plans"
    seen: dict[Path, float] = {}
    while not stop.is_set():
        try:
            for md_file in plans_dir.glob("*/feedback/*.md"):
                mtime = md_file.stat().st_mtime
                if seen.get(md_file) != mtime:
                    seen[md_file] = mtime
                    _process_feedback_file(md_file)
        except Exception:
            logger.warning("feedback watcher error", exc_info=True)
        stop.wait(2.0)


@app.route("/next_action", methods=["POST"])
def next_action_endpoint():
    """Call next_action FSM function.

    Expects JSON POST with fields:
      - flow (str): Flow name (e.g. 'team')
      - topic (str): Feature/topic name
      - project_root (str): Absolute path to project root
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        # Validate required fields
        required = {"flow", "topic", "project_root"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        for field in ("flow", "topic", "project_root"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )

        result = next_action(data)
        return jsonify(result), 200
    except Exception as e:
        logging.exception("next_action error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/complete_stage", methods=["POST"])
def complete_stage_endpoint():
    """Call complete_stage FSM function.

    Expects JSON POST with fields:
      - flow (str): Flow name (e.g. 'team')
      - topic (str): Feature/topic name
      - project_root (str): Absolute path to project root
      - decision (str, optional): Decision key for decide-blocks
      - resolved_files (list[str], optional): Feedback files to delete
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        # Validate required fields
        required = {"flow", "topic", "project_root"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        for field in ("flow", "topic", "project_root"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )

        result = complete_stage(data)
        return jsonify(result), 200
    except Exception as e:
        logging.exception("complete_stage error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


def _append_agent_done_event(
    *,
    project_root: str,
    feature: str,
    agent: str,
    model: str,
    result: str,
    conversation: object,
    total_tokens: int,
    tokens_in: int,
    tokens_out: int,
    tool_uses: int,
    wall_seconds: int,
    cost_usd: float,
) -> None:
    """Append an AGENT_DONE event to the feature's EVENTS.jsonl so SSE subscribers see it."""
    try:
        events_path = Path(project_root) / "pathly" / "plans" / feature / "EVENTS.jsonl"
        if not events_path.parent.exists():
            return
        event: dict[str, object] = {
            "schema_version": 1,
            "type": "AGENT_DONE",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "agent": agent,
            "model": model,
            "result": result,
            "total_tokens": total_tokens,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "tool_uses": tool_uses,
            "wall_seconds": wall_seconds,
            "cost_usd": cost_usd,
        }
        if conversation is not None:
            event["conversation"] = conversation
        with open(events_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        logger.debug("_append_agent_done_event error", exc_info=True)


@app.route("/record_activity", methods=["POST"])
def record_activity_endpoint():
    """Append an activity record to ~/.pathly/activity.jsonl."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"agent", "feature", "summary"}
        missing = required - set(data.keys())
        if missing:
            return (
                jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}),
                400,
            )

        for field in ("agent", "feature", "summary"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                return (
                    jsonify({"error": f"Field '{field}' must be a non-empty string"}),
                    400,
                )
        for field in ("input_tokens", "output_tokens"):
            val = data.get(field, 0)
            if not isinstance(val, (int, float)) or val < 0:
                return (
                    jsonify(
                        {"error": f"Field '{field}' must be a non-negative number"}
                    ),
                    400,
                )
        for field in ("wall_seconds", "tool_uses"):
            val = data.get(field, 0)
            if not isinstance(val, int) or val < 0:
                return (
                    jsonify(
                        {"error": f"Field '{field}' must be a non-negative integer"}
                    ),
                    400,
                )
        for field in ("total_tokens", "duration_ms"):
            val = data.get(field, 0)
            if not isinstance(val, int) or val < 0:
                return (
                    jsonify(
                        {"error": f"Field '{field}' must be a non-negative integer"}
                    ),
                    400,
                )
        cost_usd_val = data.get("cost_usd", 0.0)
        if not isinstance(cost_usd_val, (int, float)) or cost_usd_val < 0:
            return (
                jsonify({"error": "Field 'cost_usd' must be a non-negative number"}),
                400,
            )

        wall_seconds = int(data.get("wall_seconds", 0))
        duration_ms = int(data.get("duration_ms", 0))
        if wall_seconds == 0 and duration_ms > 0:
            wall_seconds = duration_ms // 1000

        if flags.telemetry:
            append_activity(
                agent=data["agent"],
                feature=data["feature"],
                summary=data["summary"],
                input_tokens=int(data.get("input_tokens", 0)),
                output_tokens=int(data.get("output_tokens", 0)),
                wall_seconds=wall_seconds,
                tool_uses=int(data.get("tool_uses", 0)),
                cost_usd=float(data.get("cost_usd", 0.0)),
                total_tokens=int(data.get("total_tokens", 0)),
            )

        project_root = data.get("project_root", "")
        if project_root and data.get("feature"):
            total_tokens = int(data.get("total_tokens", 0))
            tokens_in = int(data.get("input_tokens", 0))
            tokens_out = int(data.get("output_tokens", 0))
            if tokens_in == 0 and tokens_out == 0 and total_tokens > 0:
                tokens_in = total_tokens
            _append_agent_done_event(
                project_root=str(project_root),
                feature=str(data["feature"]),
                agent=str(data["agent"]),
                model=str(data.get("model", "")),
                result=str(data.get("result", "DONE")),
                conversation=data.get("conversation"),
                total_tokens=total_tokens,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                tool_uses=int(data.get("tool_uses", 0)),
                wall_seconds=wall_seconds,
                cost_usd=float(data.get("cost_usd", 0.0)),
            )

        return jsonify({"status": "recorded"}), 200
    except Exception as e:
        logging.exception("record_activity error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/chat", methods=["POST", "OPTIONS"])
def chat():
    if request.method == "OPTIONS":
        from flask import Response as _Resp
        resp = _Resp()
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return resp
    return handle_chat(request)


@app.route("/events/stream", methods=["GET"])
def events_stream():
    """SSE endpoint: streams new EVENTS.jsonl lines to the Studio UI."""
    from flask import Response, stream_with_context

    if not flags.sse_streaming:
        return jsonify({"error": "SSE streaming is disabled"}), 503

    topic = request.args.get("topic", "")
    project_root = request.args.get("project_root", "")
    if not topic or not project_root:
        return jsonify({"error": "topic and project_root are required"}), 400

    resolved_root = Path(project_root).resolve()
    events_path = (
        resolved_root / "pathly" / "plans" / topic / "EVENTS.jsonl"
    ).resolve()
    if not events_path.is_relative_to(resolved_root):
        return jsonify({"error": "Invalid project_root"}), 400

    key = (topic, str(resolved_root))
    client_q: queue.Queue = queue.Queue(maxsize=100)

    with _lock:
        _clients.setdefault(key, []).append(client_q)
        _inc("pathly_sse_clients_active")
        if key not in _tailers:
            stop = threading.Event()
            _tailers[key] = stop
            threading.Thread(target=_tail_events, args=(key, stop), daemon=True).start()

    def generate():
        yield 'data: {"type":"connected"}\n\n'
        try:
            while True:
                try:
                    line = client_q.get(timeout=25)
                    yield f"data: {line}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        except GeneratorExit:
            pass
        finally:
            with _lock:
                lst = _clients.get(key, [])
                if client_q in lst:
                    lst.remove(client_q)
                    _inc("pathly_sse_clients_active", -1)
                if not lst:
                    stop_evt = _tailers.pop(key, None)
                    if stop_evt is not None:
                        stop_evt.set()
                    _clients.pop(key, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": os.environ.get("PATHLY_CORS_ORIGIN", "*"),
        },
    )


def main() -> None:
    """Start the HTTP server."""
    _setup_logging()

    settings = Settings.from_env()
    port = settings.port
    host = settings.host

    import pathly_orchestrator.http_server as _self

    _self._RATE_LIMIT_MAX = settings.rate_limit_max
    _self._RATE_LIMIT_WINDOW = settings.rate_limit_window

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


if __name__ == "__main__":
    main()
