"""SSE globals and broadcast helpers."""
from __future__ import annotations

import json
import logging
import queue
import threading

_logger = logging.getLogger("pathly.http")

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

# SSE client registry: (topic, project_root) -> list of subscriber queues
_clients: dict[tuple[str, str], list[queue.Queue]] = {}
_lock = threading.Lock()
_tailers: dict[tuple[str, str], threading.Event] = {}

# Global menu-push channel — broadcasts menu payloads to all Studio subscribers
_menu_clients: list[queue.Queue] = []
_menu_lock = threading.Lock()

# Runner SSE client registry. Keyed by topic; each value is a list of per-client queues.
_runner_clients: dict[str, list[queue.Queue]] = {}
_runner_lock = threading.Lock()

# Spawn SSE client registry — TOPIC-INDEPENDENT. A single flat list of subscriber
# queues. Studio mounts exactly one always-on subscriber here so terminal
# lifecycle events (open/kill) are delivered no matter which board/topic is
# active. This is the one place that controls opening and killing PTYs; the
# per-topic _runner_clients channel carries everything else (stage/cost/menu).
_spawn_clients: list[queue.Queue] = []
_spawn_lock = threading.Lock()

# Terminal-lifecycle event types that must reach the global spawn channel
# regardless of topic.
_SPAWN_EVENT_TYPES = frozenset({"TERMINAL_SPAWN", "TERMINAL_KILL", "TERMINAL_SIGNAL"})

# Comms SSE client registry. Keyed by scope; each value is a list of per-client queues.
_comms_clients: dict[str, list[queue.Queue]] = {}
_comms_lock = threading.Lock()

# Pushed-menu TTL timer
_push_timer: threading.Timer | None = None
_push_timer_lock = threading.Lock()


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
    from pathly_orchestrator import db as _db
    from pathly_orchestrator.event_bus import _bus

    wake = threading.Event()
    bus_key = f"FSM_EVENT:{project_root}:{topic}"

    def _on_new_event(_data: dict) -> None:
        wake.set()

    _bus.subscribe(bus_key, _on_new_event)
    try:
        conn = _db.get_db()
        last_seq = 0
        while not stop.is_set():
            try:
                events = _db.read_events(conn, project_root, topic, since_seq=last_seq)
                for event in events:
                    seq = event.get("seq", 0)
                    if seq > last_seq:
                        last_seq = seq
                    _broadcast(key, json.dumps(event))
            except Exception:
                _logger.debug("tail_events SQLite error", exc_info=True)
            wake.clear()
            wake.wait(timeout=5.0)  # woken immediately by _on_new_event, or falls back to 5s
    except Exception:
        _logger.warning("tail_events: cannot open central DB for %s/%s", topic, project_root, exc_info=True)
    finally:
        _bus.unsubscribe(bus_key, _on_new_event)


def _broadcast_spawn(payload: dict) -> None:
    """Broadcast a terminal-lifecycle event to ALL /events/spawn clients.

    Topic-independent: every connected spawn subscriber receives it. Used so the
    single central terminal listener in Studio opens/kills PTYs no matter which
    board the run was started from.
    """
    raw = json.dumps(payload)
    with _spawn_lock:
        dead = [q for q in _spawn_clients if q.full()]
        for q in dead:
            _spawn_clients.remove(q)
        for q in _spawn_clients:
            try:
                q.put_nowait(raw)
            except queue.Full:
                pass


def _broadcast_runner(topic: str, payload: dict) -> None:
    """Broadcast a runner event to all /events/runner clients subscribed to *topic*.

    Terminal-lifecycle events (open/kill) are ALSO mirrored to the topic-independent
    /events/spawn channel, so the PTY opens/closes even when the run's topic is not
    the board the user is currently viewing.
    """
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
    if payload.get("type") in _SPAWN_EVENT_TYPES:
        _broadcast_spawn(payload)


def _broadcast_comms(scope: str, payload: dict) -> None:
    """Broadcast a COMMS_UPDATE event to all /events/comms clients subscribed to *scope*."""
    try:
        raw = json.dumps(payload)
        with _comms_lock:
            clients = _comms_clients.get(scope, [])
            dead = [q for q in clients if q.full()]
            for q in dead:
                clients.remove(q)
            for q in clients:
                try:
                    q.put_nowait(raw)
                except queue.Full:
                    pass
    except Exception:
        pass
