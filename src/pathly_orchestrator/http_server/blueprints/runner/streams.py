"""SSE stream endpoints."""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
from pathlib import Path

from flask import Blueprint, jsonify, request

from pathly_orchestrator.feature_flags import flags
from ...sse import (
    _clients,
    _lock,
    _tailers,
    _tail_events,
    _menu_clients,
    _menu_lock,
    _runner_clients,
    _runner_lock,
    _spawn_clients,
    _spawn_lock,
    _comms_clients,
    _comms_lock,
)
from ...middleware import _inc

logger = logging.getLogger("pathly.http")

bp = Blueprint("streams", __name__)


@bp.route("/events/menu", methods=["GET"])
def menu_events_endpoint():
    """SSE endpoint: pushes MENU_UPDATE events whenever FSM state changes."""
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


@bp.route("/events/runner", methods=["GET"])
def runner_events_endpoint():
    """SSE endpoint: streams runner lifecycle events for a given topic."""
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


@bp.route("/events/spawn", methods=["GET"])
def spawn_events_endpoint():
    """SSE endpoint: topic-INDEPENDENT terminal lifecycle stream."""
    from flask import Response, stream_with_context

    q: queue.Queue = queue.Queue(maxsize=50)
    with _spawn_lock:
        _spawn_clients.append(q)

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
            with _spawn_lock:
                if q in _spawn_clients:
                    _spawn_clients.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@bp.route("/events/history", methods=["GET"])
def events_history():
    """Return persisted event history for a feature from the central DB."""
    from pathly_orchestrator import db as _db

    topic = request.args.get("topic", "")
    project_root = request.args.get("project_root", "")
    if not topic or not project_root:
        return jsonify({"error": "topic and project_root are required"}), 400

    try:
        limit = int(request.args.get("limit", "500"))
    except ValueError:
        limit = 500

    try:
        conn = _db.get_db()
        events = _db.read_events(conn, project_root, topic, since_seq=0)
        if limit > 0:
            events = events[-limit:]
        return jsonify(events)
    except Exception as exc:
        logger.warning(
            "events_history: DB error for %s/%s: %s", project_root, topic, exc
        )
        return jsonify([])


@bp.route("/events/stream", methods=["GET"])
def events_stream():
    """SSE endpoint: streams new events to the Studio UI."""
    from flask import Response, stream_with_context

    if not flags.sse_streaming:
        return jsonify({"error": "SSE streaming is disabled"}), 503

    topic = request.args.get("topic", "")
    project_root = request.args.get("project_root", "")
    if not topic or not project_root:
        return jsonify({"error": "topic and project_root are required"}), 400

    resolved_root = Path(project_root).resolve()
    try:
        from pathly_orchestrator.fsm_ops import _resolve_storage_path

        events_path = (
            _resolve_storage_path(None, str(resolved_root), topic) / "EVENTS.jsonl"
        ).resolve()
    except ValueError:
        # _safe_topic rejects traversal / unsafe slugs — reject cleanly, don't 500.
        return jsonify({"error": "Invalid topic"}), 400
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
        try:
            since_seq = int(request.headers.get("Last-Event-ID") or 0)
        except (ValueError, TypeError):
            since_seq = 0
        if since_seq > 0:
            try:
                from pathly_orchestrator import db as _db

                catch_conn = _db.get_db()
                for event in _db.read_events(
                    catch_conn, str(resolved_root), topic, since_seq=since_seq
                ):
                    seq = event.get("seq", 0)
                    yield f"id: {seq}\ndata: {json.dumps(event)}\n\n"
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


@bp.route("/events/comms", methods=["GET"])
def comms_events_endpoint():
    """SSE endpoint: streams COMMS_UPDATE events for a given scope."""
    from flask import Response, stream_with_context

    scope = request.args.get("scope", "global").strip() or "global"

    q: queue.Queue = queue.Queue(maxsize=50)
    with _comms_lock:
        _comms_clients.setdefault(scope, []).append(q)

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
            with _comms_lock:
                clients = _comms_clients.get(scope, [])
                if q in clients:
                    clients.remove(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
