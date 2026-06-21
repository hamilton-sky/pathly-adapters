"""In-process publish/subscribe bus for decoupling event producers from consumers.

Usage:
    from pathly_orchestrator.event_bus import _bus

    # Subscribe:
    def on_agent_done(data: dict) -> None:
        ...
    _bus.subscribe("AGENT_DONE", on_agent_done)

    # Publish (called by append_event after writing to DB):
    _bus.publish("AGENT_DONE", event_dict)

    # Unsubscribe when the consumer is torn down:
    _bus.unsubscribe("AGENT_DONE", on_agent_done)

Event-type keys used internally:
    "FSM_EVENT:{project_root}:{feature}"   — any new FSM event for a feature
    Any value from pathly_orchestrator.events (AGENT_DONE, STATE_TRANSITION, …)
"""

from __future__ import annotations

import logging
import threading
from typing import Callable

logger = logging.getLogger("pathly.event_bus")


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Callable[[dict], None]]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event_type: str, fn: Callable[[dict], None]) -> None:
        with self._lock:
            self._subscribers.setdefault(event_type, []).append(fn)

    def unsubscribe(self, event_type: str, fn: Callable[[dict], None]) -> None:
        with self._lock:
            subs = self._subscribers.get(event_type)
            if subs and fn in subs:
                subs.remove(fn)

    def publish(self, event_type: str, data: dict) -> None:
        with self._lock:
            handlers = list(self._subscribers.get(event_type, []))
        for fn in handlers:
            try:
                fn(data)
            except Exception:
                logger.debug("EventBus handler error for %s", event_type, exc_info=True)


_bus = EventBus()
