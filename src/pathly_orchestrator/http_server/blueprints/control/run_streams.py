"""Unified per-run SSE stream (unified-control-plane T3) — GET /events/runs?run_id=.

A single subscription that watches ONE run end-to-end, regardless of which topic/board/
scope it lives under. ``sse._broadcast_run_event`` tees any ``/events/runner`` or
``/events/comms`` payload that carries a ``run_id`` onto the run_id-keyed client registry
(``_run_clients``); this endpoint streams straight from it. Mirrors the ``/events/runner``
generator in ``runner/streams.py`` (same queue/keepalive/cleanup shape), including the
``pathly_sse_clients_active`` gauge bookkeeping used by ``/events/stream`` — see that file
for the proven pattern this follows.
"""

from __future__ import annotations

import logging
import queue

from flask import Blueprint, jsonify, request

from ...middleware import _inc
from ...sse import _run_clients, _run_lock

logger = logging.getLogger("pathly.http")

bp = Blueprint("control_run_streams", __name__)


@bp.route("/events/runs", methods=["GET"])
def run_events_endpoint():
    """SSE endpoint: streams every event tagged ``run_id=<run_id>``, across topics/scopes."""
    from flask import Response, stream_with_context

    run_id = request.args.get("run_id", "").strip()
    if not run_id:
        return jsonify({"error": "Query parameter 'run_id' is required"}), 400

    q: queue.Queue = queue.Queue(maxsize=50)
    with _run_lock:
        _run_clients.setdefault(run_id, []).append(q)
        _inc("pathly_sse_clients_active")

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
            with _run_lock:
                clients = _run_clients.get(run_id, [])
                if q in clients:
                    clients.remove(q)
                    _inc("pathly_sse_clients_active", -1)
                if not clients:
                    _run_clients.pop(run_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
