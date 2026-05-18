"""HTTP wrapper for pathly-fsm MCP server.

Provides REST endpoints that mimic the MCP protocol functions,
allowing tools to call pathly-fsm without relying on MCP.

Run: python -m pathly_orchestrator.http_server
Or: pathly-fsm-http

Environment variables:
  PATHLY_FSM_HTTP_PORT: Port to listen on (default 8765)
  PATHLY_FSM_HTTP_HOST: Host to bind to (default 127.0.0.1)
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
from pathlib import Path

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
    sys.exit(1)

from pathly_orchestrator.mcp_server import _next_action, _complete_stage


app = Flask(__name__)

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
    path = Path(project_root) / 'pathly' / 'plans' / topic / 'EVENTS.jsonl'
    pos = 0
    while not stop.is_set():
        try:
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    f.seek(pos)
                    for raw in f:
                        raw = raw.strip()
                        if raw:
                            _broadcast(key, raw)
                    pos = f.tell()
        except Exception:
            pass
        stop.wait(0.1)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


@app.route('/next_action', methods=['POST'])
def next_action_endpoint():
    """Wrapper for mcp_server._next_action.

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
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        result = _next_action(data)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }), 500


@app.route('/complete_stage', methods=['POST'])
def complete_stage_endpoint():
    """Wrapper for mcp_server._complete_stage.

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
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        result = _complete_stage(data)
        return jsonify(result), 200
    except Exception as e:
        import traceback
        return jsonify({
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        }), 500


@app.route('/events/stream', methods=['GET'])
def events_stream():
    """SSE endpoint: streams new EVENTS.jsonl lines to the Studio UI."""
    from flask import Response, stream_with_context

    topic = request.args.get('topic', '')
    project_root = request.args.get('project_root', '')
    if not topic or not project_root:
        return jsonify({'error': 'topic and project_root are required'}), 400

    key = (topic, project_root)
    client_q: queue.Queue = queue.Queue(maxsize=100)

    with _lock:
        _clients.setdefault(key, []).append(client_q)
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
                    yield f'data: {line}\n\n'
                except queue.Empty:
                    yield ': keepalive\n\n'
        except GeneratorExit:
            pass
        finally:
            with _lock:
                lst = _clients.get(key, [])
                if client_q in lst:
                    lst.remove(client_q)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
        }
    )


def main() -> None:
    """Start the HTTP server."""
    port = int(os.environ.get("PATHLY_FSM_HTTP_PORT", "8765"))
    host = os.environ.get("PATHLY_FSM_HTTP_HOST", "127.0.0.1")

    print(f"Starting pathly-fsm HTTP server on {host}:{port}", file=sys.stderr)
    print(f"  POST {host}:{port}/next_action", file=sys.stderr)
    print(f"  POST {host}:{port}/complete_stage", file=sys.stderr)
    print(f"  GET  {host}:{port}/health", file=sys.stderr)
    print(f"  GET  {host}:{port}/events/stream?topic=TOPIC&project_root=PATH", file=sys.stderr)

    # Run Flask in non-debug mode, with warnings suppressed
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
