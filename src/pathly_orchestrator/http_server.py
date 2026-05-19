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

import json
import logging
import os
import queue
import re
import sys
import threading
import time
from pathlib import Path

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("Error: Flask not installed. Install with: pip install flask", file=sys.stderr)
    sys.exit(1)

from pathly_orchestrator.fsm_ops import next_action, complete_stage
from pathly_telemetry.storage import append_activity


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


_ARCH_QUESTION = re.compile(r"\b(architect|architecture|architectural|design|approach|structure)\b", re.IGNORECASE)
_TTL_KEY = "ttl_hours"
_TTL_LINE = "ttl_hours: 48"
_FENCE = "---"


def _classify_content(content: str) -> str:
    lines = content.splitlines()
    tagged = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("- ") and not stripped.startswith("- [REQ]") and not stripped.startswith("- [ARCH]"):
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
        pass


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
            pass
        stop.wait(2.0)


@app.route('/next_action', methods=['POST'])
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
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        result = next_action(data)
        return jsonify(result), 200
    except Exception as e:
        logging.exception("next_action error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/complete_stage', methods=['POST'])
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
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        result = complete_stage(data)
        return jsonify(result), 200
    except Exception as e:
        logging.exception("complete_stage error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/record_activity', methods=['POST'])
def record_activity_endpoint():
    """Append an activity record to ~/.pathly/activity.jsonl."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        required = {"agent", "feature", "summary"}
        missing = required - set(data.keys())
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(sorted(missing))}"}), 400

        append_activity(
            agent=data["agent"],
            feature=data["feature"],
            summary=data["summary"],
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
        )
        return jsonify({"status": "recorded"}), 200
    except Exception as e:
        logging.exception("record_activity error")
        return jsonify({"error": str(e), "type": type(e).__name__}), 500


@app.route('/events/stream', methods=['GET'])
def events_stream():
    """SSE endpoint: streams new EVENTS.jsonl lines to the Studio UI."""
    from flask import Response, stream_with_context

    topic = request.args.get('topic', '')
    project_root = request.args.get('project_root', '')
    if not topic or not project_root:
        return jsonify({'error': 'topic and project_root are required'}), 400

    resolved_root = Path(project_root).resolve()
    events_path = (resolved_root / 'pathly' / 'plans' / topic / 'EVENTS.jsonl').resolve()
    if not events_path.is_relative_to(resolved_root):
        return jsonify({"error": "Invalid project_root"}), 400

    key = (topic, str(resolved_root))
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
                if not lst:
                    stop_evt = _tailers.pop(key, None)
                    if stop_evt is not None:
                        stop_evt.set()
                    _clients.pop(key, None)

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

    project_root = os.environ.get("PATHLY_PROJECT_ROOT", "")
    _watcher_stop = threading.Event()
    if project_root:
        threading.Thread(target=_feedback_watcher, args=(project_root, _watcher_stop), daemon=True).start()

    # Run Flask in non-debug mode, with warnings suppressed
    app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
