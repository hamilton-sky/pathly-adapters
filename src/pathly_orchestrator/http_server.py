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
import sys
from pathlib import Path

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
    sys.exit(1)

from pathly_orchestrator.mcp_server import _next_action, _complete_stage


app = Flask(__name__)


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


def main() -> None:
    """Start the HTTP server."""
    port = int(os.environ.get("PATHLY_FSM_HTTP_PORT", "8765"))
    host = os.environ.get("PATHLY_FSM_HTTP_HOST", "127.0.0.1")

    print(f"Starting pathly-fsm HTTP server on {host}:{port}", file=sys.stderr)
    print(f"  POST {host}:{port}/next_action", file=sys.stderr)
    print(f"  POST {host}:{port}/complete_stage", file=sys.stderr)
    print(f"  GET  {host}:{port}/health", file=sys.stderr)

    # Run Flask in non-debug mode, with warnings suppressed
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
