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
from pathly_orchestrator import eventlog
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
    # Health endpoint bypasses all middleware — must respond before rate-limiting.
    if request.path == "/health":
        return None

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

# Global menu-push channel — broadcasts menu payloads to all Studio subscribers
_menu_clients: list[queue.Queue] = []
_menu_lock = threading.Lock()


def _broadcast_sse(payload: dict) -> None:
    """Generic SSE broadcast to all connected /events/menu clients."""
    raw = json.dumps(payload)
    with _menu_lock:
        dead = [q for q in _menu_clients if q.full()]
        for q in dead:
            _menu_clients.remove(q)
        for q in _menu_clients:
            try:
                q.put_nowait(raw)
            except queue.Full:
                pass


def _push_menu_to_sse(menu: dict) -> None:
    """Broadcast a pipeline MENU_UPDATE to all connected /events/menu SSE clients."""
    _broadcast_sse({"type": "MENU_UPDATE", "menu": menu})


# ── Pushed-menu TTL timer ────────────────────────────────────────────────────
_push_timer: threading.Timer | None = None
_push_timer_lock = threading.Lock()


def _fire_push_clear() -> None:
    global _push_timer
    with _push_timer_lock:
        _push_timer = None
    _broadcast_sse({"type": "MENU_CLEAR"})


def _schedule_push_clear(ttl: float) -> None:
    global _push_timer
    with _push_timer_lock:
        if _push_timer is not None:
            _push_timer.cancel()
        t = threading.Timer(ttl, _fire_push_clear)
        t.daemon = True
        t.start()
        _push_timer = t


def _broadcast(key: tuple[str, str], line: str) -> None:
    with _lock:
        for q in _clients.get(key, []):
            try:
                q.put_nowait(line)
            except queue.Full:
                pass


def _tail_events(key: tuple[str, str], stop: threading.Event) -> None:
    topic, project_root = key
    feature_dir = Path(project_root) / "pathly" / "plans" / topic
    db_path = feature_dir / "pathly.db"

    if db_path.exists():
        from pathly_orchestrator import db as _db
        try:
            conn = _db.get_db(feature_dir)
        except Exception:
            logger.debug("tail_events: cannot open SQLite DB, falling back to file", exc_info=True)
            conn = None
        if conn is not None:
            last_seq = 0
            while not stop.is_set():
                try:
                    events = _db.read_events(conn, topic, since_seq=last_seq)
                    for event in events:
                        seq = event.get("seq", 0)
                        if seq > last_seq:
                            last_seq = seq
                        _broadcast(key, json.dumps(event))
                except Exception:
                    logger.debug("tail_events SQLite error", exc_info=True)
                stop.wait(0.1)
            return

    path = feature_dir / "EVENTS.jsonl"
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


@app.route("/shutdown", methods=["POST"])
def shutdown():
    """Graceful shutdown — lets Studio restart with updated code."""
    threading.Timer(0.1, lambda: os._exit(0)).start()
    return jsonify({"ok": True})


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

    topic = request.args.get("topic", "").strip()
    best_state: dict | None = None
    best_state_dir: Path | None = None

    if topic:
        # Specific topic requested — read directly, skip the glob.
        topic_dir = plans_dir / topic
        try:
            if not topic_dir.resolve().is_relative_to(resolved_root):
                return jsonify({"error": "Invalid topic"}), 400
        except Exception:
            return jsonify({"error": "Invalid topic"}), 400
        if topic_dir.is_dir():
            best_state = read_state(str(topic_dir))
            if best_state is not None:
                best_state_dir = topic_dir
    else:
        # Find the most recently updated STATE.json across all features.
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
                            best_state_dir = state_file.parent
                except Exception:
                    logger.debug("status: error reading %s", state_file, exc_info=True)
        except Exception:
            logger.debug("status: error scanning plans dir", exc_info=True)
            return jsonify({"current_state": "unknown"}), 200

    if best_state is None:
        return jsonify({"current_state": "no-feature", "feature": "", "project_root": project_root, "menu": _NO_FEATURE_MENU}), 200

    # Infer feature from directory name when STATE.json lacks the field.
    feature = best_state.get("feature", "") or (best_state_dir.name if best_state_dir else "")

    menu = None
    try:
        from importlib.resources import files
        import yaml

        flow_config = yaml.safe_load(
            files("pathly_data").joinpath("core/flows/team.flow.yaml").read_text(encoding="utf-8")
        )
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
            "feature": feature,
            "project_root": project_root,
            "menu": menu,
        }
    ), 200


@app.route("/menu/<name>", methods=["GET"])
def get_named_menu(name: str):
    """Return a pre-defined named menu, broadcast it as MENU_PUSH via SSE, start TTL.

    Query params:
      feature (optional): substituted into {feature} placeholders in title/descriptions.
      state   (optional): FSM state name (e.g. BUILDING); items whose `states:` list
                          does not include this state are filtered out.  Items with no
                          `states:` field are always included.

    The Studio Conductor shows the menu until TTL expires (MENU_CLEAR SSE event)
    or the user dismisses it.  Skills call this endpoint instead of rendering
    ASCII menus in the terminal.
    """
    feature = request.args.get("feature", "").strip()
    state = request.args.get("state", "").strip().upper()

    try:
        from importlib.resources import files as _res_files
        import yaml as _yaml
        all_menus = _yaml.safe_load(
            _res_files("pathly_data").joinpath("core/menus.yaml").read_text(encoding="utf-8")
        ) or {}
    except Exception:
        logger.debug("get_named_menu: failed to load menus.yaml", exc_info=True)
        return jsonify({"error": "Menu registry unavailable"}), 503

    if name not in all_menus:
        return jsonify({"error": f"Unknown menu: '{name}'"}), 404

    raw = all_menus[name]
    ttl = float(raw.get("ttl", 60))
    pushed_at_ms = int(time.time() * 1000)

    def sub(text: str) -> str:
        return text.replace("{feature}", feature) if feature and isinstance(text, str) else (text or "")

    menu = {
        "state": name,
        "feature": feature,
        "agent": "director",
        "title": sub(raw.get("title", name)),
        "subtitle": sub(raw.get("subtitle", "")),
        "items": [
            {
                "label": item.get("label", ""),
                "description": sub(item.get("description", "")),
                "command": item.get("command", ""),
                "terminal_kind": item.get("terminal_kind", "claude"),
            }
            for item in raw.get("items", [])
            if not item.get("states") or not state or state in [s.upper() for s in item["states"]]
        ],
        "empty_message": raw.get("empty_message", "No options available."),
        "ttl": ttl,
        "pushed_at": pushed_at_ms,
    }

    _broadcast_sse({"type": "MENU_PUSH", "menu": menu})
    _schedule_push_clear(ttl)

    return jsonify({"status": "pushed", "menu": menu}), 200


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
        if isinstance(result.get("menu"), dict):
            _push_menu_to_sse(result["menu"])
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
        if isinstance(result.get("menu"), dict):
            _push_menu_to_sse(result["menu"])
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
    trace_id: str = "",
    span_id: str = "",
) -> None:
    """Append an AGENT_DONE event to the feature's EVENTS.jsonl so SSE subscribers see it."""
    try:
        feature_dir = Path(project_root) / "pathly" / "plans" / feature
        if not feature_dir.exists():
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
        if trace_id:
            event["trace_id"] = trace_id
        if span_id:
            event["span_id"] = span_id
        eventlog.append_event(str(feature_dir), event)
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

        # Server-side cost computation: if cost_usd is 0.0 but model + tokens are provided,
        # compute using the canonical Pathly pricing table (same table as log-agent-done skill).
        # Covers any adapter that passes model + tokens but not cost_usd.
        if float(cost_usd_val) == 0.0:
            _model = str(data.get("model", ""))
            _total = int(data.get("total_tokens", 0)) or int(data.get("input_tokens", 0)) + int(data.get("output_tokens", 0))
            if _model and _total > 0:
                _PRICING: dict[str, tuple[float, float]] = {
                    "claude-opus-4":    (15.00, 75.00),
                    "claude-sonnet-4":  ( 3.00, 15.00),
                    "claude-haiku-4":   ( 0.80,  4.00),
                }
                _in_rate, _out_rate = next(
                    (v for k, v in _PRICING.items() if _model.startswith(k)),
                    (0.0, 0.0),
                )
                if _in_rate > 0:
                    _in_tok  = int(data.get("input_tokens",  0)) or round(_total * 0.8)
                    _out_tok = int(data.get("output_tokens", 0)) or round(_total * 0.2)
                    cost_usd_val = round(
                        (_in_tok / 1_000_000 * _in_rate) + (_out_tok / 1_000_000 * _out_rate), 6
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
                cost_usd=float(cost_usd_val),
                total_tokens=int(data.get("total_tokens", 0)),
            )

        trace_id = data.get("trace_id", "")
        span_id = data.get("span_id", "")

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
                cost_usd=float(cost_usd_val),
                trace_id=str(trace_id) if trace_id else "",
                span_id=str(span_id) if span_id else "",
            )
            # OTel export — fire-and-forget; no-op if PATHLY_OTEL_ENDPOINT is unset
            try:
                from pathly_orchestrator import otel_export as _otel
                _otel.export_span_async({
                    "type": "AGENT_DONE",
                    "agent": str(data["agent"]),
                    "feature": str(data["feature"]),
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "result": str(data.get("result", "DONE")),
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "cost_usd": float(cost_usd_val),
                    "wall_seconds": wall_seconds,
                    "model": str(data.get("model", "")),
                    "conversation": data.get("conversation"),
                    "summary": str(data.get("summary", "")),
                    "trace_id": str(data.get("trace_id", "")),
                    "span_id": str(data.get("span_id", "")),
                })
            except Exception:
                logger.debug("otel_export hook error", exc_info=True)

        return jsonify({"status": "recorded"}), 200
    except Exception as e:
        logging.exception("record_activity error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


_VALID_PHASES = {"analyze", "build", "design", "implement", "plan", "review", "scout", "storm", "test"}
_VALID_EVENT_TYPES = {"PHASE_START", "PHASE_DONE"}


@app.route("/record_phase", methods=["POST"])
def record_phase_endpoint():
    """Append a PHASE_START or PHASE_DONE event to the feature's EVENTS.jsonl."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = ("feature", "agent", "phase", "event_type")
        for field in required:
            if field not in data:
                return jsonify({"error": f"Missing required field: '{field}'"}), 400
            if not isinstance(data[field], str) or not data[field].strip():
                return jsonify({"error": f"Field '{field}' must be a non-empty string"}), 400

        event_type = data["event_type"]
        if event_type not in _VALID_EVENT_TYPES:
            return jsonify({"error": f"Invalid event_type '{event_type}'; must be one of {sorted(_VALID_EVENT_TYPES)}"}), 400

        phase = data["phase"]
        if phase not in _VALID_PHASES:
            return jsonify({"error": f"Invalid phase '{phase}'; must be one of {sorted(_VALID_PHASES)}"}), 400

        feature = data["feature"]
        project_root = data.get("project_root") or os.environ.get("PATHLY_PROJECT_ROOT", "")
        if project_root:
            feature_dir = Path(project_root) / "pathly" / "plans" / feature
        else:
            feature_dir = Path("pathly") / "plans" / feature

        if not feature_dir.exists():
            return jsonify({"error": f"Feature directory does not exist: {feature_dir}"}), 400

        event: dict[str, object] = {
            "schema_version": 1,
            "type": event_type,
            "phase": phase,
            "agent": data["agent"],
            "feature": feature,
        }
        if data.get("conv") is not None:
            event["conv"] = data["conv"]
        if event_type == "PHASE_DONE":
            for field in ("total_tokens", "tool_uses", "scouts_count"):
                if data.get(field) is not None:
                    event[field] = data[field]
        if data.get("summary") is not None:
            event["summary"] = data["summary"]
        event["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        eventlog.append_event(str(feature_dir), event)

        return jsonify({"status": "recorded"}), 200
    except Exception as e:
        logging.exception("record_phase error")
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


@app.route("/events/menu", methods=["GET"])
def menu_events_endpoint():
    """SSE endpoint: pushes MENU_UPDATE events whenever FSM state changes.

    The Studio renderer subscribes here with EventSource so the PathlyMenuCard
    updates the instant Claude calls /next_action or /complete_stage —
    no polling delay.
    """
    from flask import Response, stream_with_context

    q: queue.Queue = queue.Queue(maxsize=50)
    with _menu_lock:
        _menu_clients.append(q)

    def generate():
        try:
            yield 'data: {"type":"connected"}\n\n'
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _menu_lock:
                if q in _menu_clients:
                    _menu_clients.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Runner SSE client registry ───────────────────────────────────────────────
# Keyed by topic; each value is a list of per-client queues.
_runner_clients: dict[str, list[queue.Queue]] = {}
_runner_lock = threading.Lock()


def _broadcast_runner(topic: str, payload: dict) -> None:
    """Broadcast a runner event to all /events/runner clients subscribed to *topic*."""
    raw = json.dumps(payload)
    with _runner_lock:
        clients = _runner_clients.get(topic, [])
        dead = [q for q in clients if q.full()]
        for q in dead:
            clients.remove(q)
        for q in clients:
            try:
                q.put_nowait(raw)
            except queue.Full:
                pass


# ── /runner/* control endpoints ───────────────────────────────────────────────

def _topic_from_body(data: dict) -> str | None:
    topic = data.get("topic", "")
    return topic if isinstance(topic, str) and topic.strip() else None


@app.route("/runner/start", methods=["POST"])
def runner_start():
    """Start a supervised run for a topic.

    Required body fields: topic, flow, project_root, max_iterations, max_cost_usd.
    Returns 409 if a run for that topic is already active.
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"topic", "flow", "project_root", "max_iterations", "max_cost_usd"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        topic = data.get("topic", "")
        if not isinstance(topic, str) or not topic.strip():
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        for field_name in ("flow", "project_root"):
            val = data.get(field_name, "")
            if not isinstance(val, str) or not val.strip():
                return jsonify({"error": f"Field '{field_name}' must be a non-empty string"}), 400

        max_iterations = data.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            return jsonify({"error": "Field 'max_iterations' must be a positive integer"}), 400

        max_cost_usd = data.get("max_cost_usd")
        if not isinstance(max_cost_usd, (int, float)) or max_cost_usd <= 0:
            return jsonify({"error": "Field 'max_cost_usd' must be a positive number"}), 400

        model = data.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"
        timeout = data.get("timeout", 600)
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = 600
        autonomy = data.get("autonomy", {})
        if not isinstance(autonomy, dict):
            autonomy = {}
        # interactive: True = visible PTY killed on AGENT_DONE, False = headless/reconciliation
        interactive = data.get("interactive", True)
        if not isinstance(interactive, bool):
            interactive = bool(interactive)

        state = _sup.start_run(
            topic=topic,
            flow=data["flow"],
            project_root=data["project_root"],
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=float(max_cost_usd),
            autonomy=autonomy,
            broadcast_fn=_broadcast_runner,
            interactive=interactive,
        )
        return jsonify({"status": "started", "topic": topic, "run_id": state.run_id}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_start error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/terminal/started", methods=["POST"])
def runner_terminal_started():
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        run_id = data.get("run_id", "")
        if not topic or not isinstance(run_id, str) or not run_id:
            return jsonify({"error": "unknown run_id"}), 404
        with _sup._lock:
            evt = _sup._terminal_started_events.get(run_id)
            if evt is None:
                return jsonify({"error": "unknown run_id"}), 404
            evt.set()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_terminal_started error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/terminal/result", methods=["POST"])
def runner_terminal_result():
    try:
        from pathly_orchestrator import supervisor as _sup
        from pathly_orchestrator.runner import parse_result

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        run_id = data.get("run_id", "")
        if not topic or not isinstance(run_id, str) or not run_id:
            return jsonify({"error": "unknown run_id"}), 404

        with _sup._lock:
            evt = _sup._terminal_result_events.get(run_id)
            if evt is None:
                return jsonify({"error": "unknown run_id"}), 404
            runner_state = _sup._registry.get(topic)
            if runner_state is not None:
                adapter = runner_state.current_adapter or "claude"
            else:
                logger.warning("runner_terminal_result: no RunnerState found for topic %r, falling back to 'claude'", topic)
                adapter = "claude"

        # Parse stdout result (session_id + cost_usd) — outside the lock
        parsed = parse_result(adapter, data.get("stdout_tail", ""))

        # Enrich with EVENTS.jsonl summary (authoritative, never truncated)
        if runner_state is not None:
            try:
                from pathly_orchestrator.runner import read_last_agent_done, _storage_path
                storage = _storage_path(runner_state.flow, runner_state.project_root, runner_state.topic)
                agent_done = read_last_agent_done(storage)
                if agent_done is not None:
                    summary = agent_done.get("summary", "")
                    if summary:
                        parsed["result"] = summary
                    # Use EVENTS.jsonl cost as fallback when stdout didn't capture it
                    if not parsed.get("cost_usd") and agent_done.get("cost_usd", 0.0) > 0.0:
                        parsed["cost_usd"] = agent_done["cost_usd"]
            except Exception as exc:
                logger.warning("runner_terminal_result: EVENTS.jsonl read failed: %s", exc)

        # Broadcast STAGE_RESULT so Studio renderer can update the stageLog
        # directly — this is the reliable path when PTY stdout parsing fails
        # (e.g. long-running builds where the final JSON scrolls out of the buffer).
        tab_id = runner_state.active_tab_id if runner_state is not None else ""
        if tab_id and topic:
            _broadcast_runner(topic, {
                "type": "STAGE_RESULT",
                "topic": topic,
                "run_id": run_id,
                "tab_id": tab_id,
                "result": parsed.get("result", ""),
                "total_cost_usd": parsed.get("cost_usd", 0.0),
                "duration_ms": int((data.get("wall_seconds") or 0) * 1000),
                "usage": parsed.get("usage", {}),
            })

        with _sup._lock:
            _sup._terminal_result_data[run_id] = {
                "result": parsed,
                "exit_code": data.get("exit_code"),
                "wall_seconds": data.get("wall_seconds"),
                "user_initiated": data.get("user_initiated"),
            }
            evt.set()
        return jsonify({"ok": True}), 200
    except Exception as exc:
        logging.exception("runner_terminal_result error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/pause", methods=["POST"])
def runner_pause():
    """Pause an active run at its next boundary."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.pause_run(topic)
        return jsonify({"status": "pausing", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": f"No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_pause error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/resume", methods=["POST"])
def runner_resume():
    """Resume a paused run."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.resume_run(topic)
        return jsonify({"status": "resumed", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_resume error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/advance", methods=["POST"])
def runner_advance():
    """Advance a paused run by one stage (resume + re-pause after next boundary).

    This is a thin control shim — it unpauses the loop; the boundary logic in
    the supervisor handles the actual step semantics.
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.resume_run(topic)
        return jsonify({"status": "advancing", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_advance error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/decision", methods=["POST"])
def runner_decision():
    """Supply a decision for an awaiting_decision run.

    Required: topic, decision (must be a key in pending_menu.options).
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        decision = data.get("decision", "")
        if not isinstance(decision, str) or not decision.strip():
            return jsonify({"error": "Field 'decision' must be a non-empty string"}), 400

        state = _sup.get_state(topic)
        if state is None:
            return jsonify({"error": "No run found for topic"}), 404
        if state.status != "awaiting_decision":
            return jsonify({"error": f"Run is not awaiting a decision (status={state.status})"}), 409

        if state.pending_menu:
            options = state.pending_menu.get("options", {})
            if options and decision not in options:
                return jsonify({"error": f"Invalid decision {decision!r}; valid options: {list(options)}"}), 400

        _sup.supply_decision(topic, decision)
        return jsonify({"status": "accepted", "topic": topic, "decision": decision}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_decision error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/agent-answer", methods=["POST"])
def runner_agent_answer():
    """Supply a user answer for a stage that asked a question via AskUserQuestion (denied in headless mode)."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        answer = data.get("answer", "")
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        if not isinstance(answer, str) or not answer.strip():
            return jsonify({"error": "Field 'answer' must be a non-empty string"}), 400

        _sup.supply_agent_answer(topic, answer.strip())
        return jsonify({"status": "accepted", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_agent_answer error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/reroute", methods=["POST"])
def runner_reroute():
    """Override the adapter for the next stage of an active run."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        adapter = data.get("adapter", "")
        if not isinstance(adapter, str) or not adapter.strip():
            return jsonify({"error": "Field 'adapter' must be a non-empty string"}), 400

        _sup.reroute_run(topic, adapter)
        return jsonify({"status": "rerouted", "topic": topic, "adapter": adapter}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_reroute error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/retry", methods=["POST"])
def runner_retry():
    """Retry a run that ended in error by starting it fresh.

    Thin wrapper: clears error state from registry then delegates to start_run
    with the same parameters.  Requires full start params (caps required).
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400

        state = _sup.get_state(topic)
        if state is not None and state.status in {"running", "paused", "awaiting_decision"}:
            return jsonify({"error": f"Run is currently active (status={state.status}); abort it first"}), 409

        # Evict from registry so start_run won't reject it as active
        from pathly_orchestrator.supervisor import _lock, _registry
        with _lock:
            _registry.pop(topic, None)

        required = {"flow", "project_root", "max_iterations", "max_cost_usd"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        max_iterations = data.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            return jsonify({"error": "Field 'max_iterations' must be a positive integer"}), 400

        max_cost_usd = data.get("max_cost_usd")
        if not isinstance(max_cost_usd, (int, float)) or max_cost_usd <= 0:
            return jsonify({"error": "Field 'max_cost_usd' must be a positive number"}), 400

        model = data.get("model", "claude-sonnet-4-6") or "claude-sonnet-4-6"
        timeout = data.get("timeout", 600)
        if not isinstance(timeout, int) or timeout <= 0:
            timeout = 600
        autonomy = data.get("autonomy", {})
        if not isinstance(autonomy, dict):
            autonomy = {}

        _sup.start_run(
            topic=topic,
            flow=data["flow"],
            project_root=data["project_root"],
            model=model,
            timeout=timeout,
            max_iterations=max_iterations,
            max_cost_usd=float(max_cost_usd),
            autonomy=autonomy,
            broadcast_fn=_broadcast_runner,
        )
        return jsonify({"status": "retried", "topic": topic}), 200
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except Exception as exc:
        logging.exception("runner_retry error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/abort", methods=["POST"])
def runner_abort():
    """Hard-abort an active run; kills in-flight subprocess within ~2s."""
    try:
        from pathly_orchestrator import supervisor as _sup

        data = request.get_json() or {}
        topic = _topic_from_body(data)
        if not topic:
            return jsonify({"error": "Field 'topic' must be a non-empty string"}), 400
        _sup.abort_run(topic)
        return jsonify({"status": "aborting", "topic": topic}), 200
    except KeyError:
        return jsonify({"error": "No run found for topic"}), 404
    except Exception as exc:
        logging.exception("runner_abort error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/runner/status", methods=["GET"])
def runner_status():
    """Return the current RunnerState for a topic.

    Query param: topic (required).
    """
    try:
        from pathly_orchestrator import supervisor as _sup

        topic = request.args.get("topic", "").strip()
        if not topic:
            return jsonify({"error": "Query parameter 'topic' is required"}), 400

        state = _sup.get_state(topic)
        if state is None:
            return jsonify({"error": "No run found for topic"}), 404

        return jsonify(state.public_dict()), 200
    except Exception as exc:
        logging.exception("runner_status error")
        return jsonify({"error": str(exc), "type": type(exc).__name__}), 500


@app.route("/events/runner", methods=["GET"])
def runner_events_endpoint():
    """SSE endpoint: streams runner lifecycle events for a given topic.

    Query param: topic (required).

    Event types (see FEATURE_INDEX.md):
      connected, STAGE_CHANGE, DECISION_MENU, RUNNER_STATUS, COST_UPDATE, SESSION, RUNNER_ERROR
    """
    from flask import Response, stream_with_context

    topic = request.args.get("topic", "").strip()
    if not topic:
        return jsonify({"error": "Query parameter 'topic' is required"}), 400

    q: queue.Queue = queue.Queue(maxsize=50)
    with _runner_lock:
        _runner_clients.setdefault(topic, []).append(q)

    def generate():
        try:
            yield 'data: {"type":"connected"}\n\n'
            while True:
                try:
                    data = q.get(timeout=25)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _runner_lock:
                clients = _runner_clients.get(topic, [])
                if q in clients:
                    clients.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
        # Catch-up for reconnecting clients
        try:
            since_seq = int(request.headers.get("Last-Event-ID") or 0)
        except (ValueError, TypeError):
            since_seq = 0
        if since_seq > 0:
            try:
                feature_dir = resolved_root / "pathly" / "plans" / topic
                db_path = feature_dir / "pathly.db"
                if db_path.exists():
                    from pathly_orchestrator import db as _db
                    catch_conn = _db.get_db(feature_dir)
                    try:
                        for event in _db.read_events(catch_conn, topic, since_seq=since_seq):
                            seq = event.get("seq", 0)
                            yield f"id: {seq}\ndata: {json.dumps(event)}\n\n"
                    finally:
                        catch_conn.close()
            except Exception:
                logger.debug("SSE catch-up error for topic %s", topic, exc_info=True)
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


@app.route("/skills/catalog", methods=["GET"])
def skills_catalog():
    """Return the fragment catalog for the skill notebook editor."""
    try:
        from pathly_orchestrator.skill_catalog import read_fragment_catalog
        from importlib.resources import files as _res_files

        core_skills_dir = str(_res_files("pathly_data").joinpath("core/skills"))
        catalog = read_fragment_catalog(core_skills_dir)
        return jsonify(catalog), 200
    except Exception as e:
        logging.exception("skills_catalog error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/skills/parse", methods=["POST"])
def skills_parse():
    """Parse a skill .md file into body cells and fragment cells.

    Body: {"skill_path": "src/pathly_data/core/skills/team/build.md"}
    Returns: {"body_cells": [...], "fragment_cells": [...], "composition_key": "team/build"}
    """
    try:
        import uuid as _uuid
        import yaml as _yaml
        from pathly_orchestrator.skill_parser import parse_skill_body

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill_path = data.get("skill_path", "")
        if not isinstance(skill_path, str) or not skill_path.strip():
            return jsonify({"error": "Field 'skill_path' must be a non-empty string"}), 400

        cells = parse_skill_body(skill_path)

        # Derive composition_key from path: strip leading dirs down to team/build form
        # Normalize slashes and strip any known prefix to arrive at skill name
        normalized = skill_path.replace("\\", "/")
        # Remove everything up to and including "core/skills/"
        marker = "core/skills/"
        idx = normalized.find(marker)
        if idx != -1:
            rel = normalized[idx + len(marker):]
        else:
            rel = normalized.split("/")[-1]
        composition_key = rel.removesuffix(".md")

        # Load fragment cells from composition.yaml if the skill is listed there
        fragment_cells: list[dict] = []
        skills_dir_idx = normalized.find(marker)
        if skills_dir_idx != -1:
            skills_dir = normalized[: skills_dir_idx + len(marker)]
            composition_path = skills_dir + "composition.yaml"
            try:
                with open(composition_path, encoding="utf-8") as f:
                    comp = _yaml.safe_load(f)
                skill_entry = (comp.get("skills") or {}).get(composition_key)
                if skill_entry:
                    fragments_dir = (comp.get("fragments_dir") or "fragments")
                    defaults = comp.get("defaults") or []
                    all_fragment_names = list(defaults) + list(skill_entry.get("fragments") or [])
                    for frag in all_fragment_names:
                        if isinstance(frag, dict):
                            frag_name = frag.get("name", "")
                        else:
                            frag_name = str(frag)
                        if not frag_name:
                            continue
                        frag_md = f"{skills_dir}{fragments_dir}/{frag_name}.md"
                        description = ""
                        try:
                            with open(frag_md, encoding="utf-8") as f:
                                first_line = f.readline().strip()
                                if first_line.startswith("##"):
                                    description = first_line.lstrip("#").strip()
                        except OSError:
                            pass
                        fragment_cells.append({
                            "id": str(_uuid.uuid4()),
                            "type": "fragment",
                            "fragmentName": frag_name,
                            "category": "core",
                            "description": description,
                        })
            except OSError:
                pass

        return jsonify({"body_cells": cells, "fragment_cells": fragment_cells, "composition_key": composition_key}), 200
    except FileNotFoundError as e:
        return jsonify({"error": str(e), "type": "FileNotFoundError"}), 404
    except Exception as e:
        logging.exception("skills_parse error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/skills/preview", methods=["POST"])
def skills_preview():
    """Preview an assembled skill with live fragment substitution.

    Body: {"skill": "team/build", "cells": [...], "feature_path": "pathly/plans/foo"}
    Returns: {"sections": [{heading, content, origin}], "tokens": int}
    """
    try:
        from pathly_orchestrator.compose import compose_skill
        from pathly_orchestrator.fsm_ops import _inject_prompt_vars

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = data.get("skill", "")
        cells = data.get("cells", [])
        feature_path = data.get("feature_path", "")

        if not isinstance(skill, str) or not skill.strip():
            return jsonify({"error": "Field 'skill' must be a non-empty string"}), 400

        # Collect fragment names from cells where type == "fragment"
        fragment_names = [
            c["fragmentName"]
            for c in (cells or [])
            if isinstance(c, dict) and c.get("type") == "fragment" and c.get("fragmentName")
        ]

        # Build adapter_caps: use fragment_names directly if provided via cells,
        # otherwise fall back to compose_skill which reads composition.yaml
        if fragment_names:
            from pathly_orchestrator.compose import _read_skill_body
            from pathly_orchestrator.compose import load_manifest, _read_fragment

            manifest = load_manifest()
            fragments_dir = manifest.get("fragments_dir", "fragments")
            try:
                skill_body = _read_skill_body(skill)
            except Exception:
                skill_body = ""
            fragment_bodies = []
            for fname in fragment_names:
                try:
                    fragment_bodies.append(_read_fragment(fragments_dir, fname).rstrip("\n"))
                except Exception:
                    pass
            parts = [skill_body.rstrip("\n")] + fragment_bodies
            assembled = "\n\n".join(parts) + "\n"
        else:
            assembled = compose_skill(skill, adapter_caps={"can_spawn": True})

        # Variable substitution
        feature = Path(feature_path).name if feature_path else ""
        project_root = str(Path(feature_path).parent.parent.parent) if feature_path else ""
        agent_role = skill.split("/")[-1] if "/" in skill else skill
        storage_path = Path(feature_path) if feature_path else None
        assembled = _inject_prompt_vars(
            assembled,
            feature=feature,
            project_root=project_root,
            agent_role=agent_role,
            storage_path=storage_path,
        )

        # Split into sections on ## headings
        import re as _re
        parts_list = _re.split(r"(?m)^(## .+)$", assembled)
        sections: list[dict] = []
        preamble = parts_list[0].strip()
        if preamble:
            sections.append({"heading": "", "content": preamble, "origin": "body"})
        for i in range(1, len(parts_list) - 1, 2):
            heading = parts_list[i].strip()
            content = parts_list[i + 1].strip() if i + 1 < len(parts_list) else ""
            sections.append({"heading": heading, "content": content, "origin": "body"})

        tokens = int(len(assembled.split()) * 1.3)
        return jsonify({"sections": sections, "tokens": tokens}), 200
    except Exception as e:
        logging.exception("skills_preview error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route("/skills/export", methods=["PUT"])
def skills_export():
    """Update composition.yaml with a new fragment_order for a skill.

    Body: {"skill": "team/build", "fragment_order": ["name1", "name2"]}
    Returns: {"ok": True}
    """
    try:
        import yaml

        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        skill = data.get("skill", "")
        fragment_order = data.get("fragment_order", [])
        if not isinstance(skill, str) or not skill.strip():
            return jsonify({"error": "Field 'skill' must be a non-empty string"}), 400
        if not isinstance(fragment_order, list):
            return jsonify({"error": "Field 'fragment_order' must be a list"}), 400

        from importlib.resources import files as _res_files
        from pathlib import Path as _Path

        # Locate the composition.yaml file on disk (importlib resources path)
        skills_resource = _res_files("pathly_data").joinpath("core/skills")
        composition_path = _Path(str(skills_resource)) / "composition.yaml"

        with open(composition_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f) or {}

        if "skills" not in manifest or manifest["skills"] is None:
            manifest["skills"] = {}
        if skill not in manifest["skills"] or manifest["skills"][skill] is None:
            manifest["skills"][skill] = {}
        manifest["skills"][skill]["fragments"] = fragment_order

        with open(composition_path, "w", encoding="utf-8") as f:
            yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        return jsonify({"ok": True}), 200
    except Exception as e:
        logging.exception("skills_export error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


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
