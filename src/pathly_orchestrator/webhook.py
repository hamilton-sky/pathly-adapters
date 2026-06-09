"""WebhookNotifier — fire-and-forget HTTP POST on configurable FSM events.

Configuration via environment variables:
    PATHLY_WEBHOOK_URL     POST target. Empty = notifier disabled.
    PATHLY_WEBHOOK_EVENTS  Comma-separated event types to forward.
                           Default: AGENT_DONE,STATE_TRANSITION,GATE_FAILED

Each notification is a JSON POST in a daemon thread so it never blocks the FSM.
Uses only stdlib (urllib) — no third-party HTTP library required.

Example (Slack incoming webhook):
    PATHLY_WEBHOOK_URL=https://hooks.slack.com/services/T.../B.../xxx \
    PATHLY_WEBHOOK_EVENTS=AGENT_DONE,STATE_TRANSITION \
    pathly-fsm-server
"""
from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request

from pathly_orchestrator.event_bus import _bus

logger = logging.getLogger("pathly.webhook")

_DEFAULT_EVENTS = "AGENT_DONE,STATE_TRANSITION,GATE_FAILED"


class WebhookNotifier:
    def __init__(self) -> None:
        self.url = os.environ.get("PATHLY_WEBHOOK_URL", "").strip()
        if not self.url:
            return  # disabled — no env var set

        events_raw = os.environ.get("PATHLY_WEBHOOK_EVENTS", _DEFAULT_EVENTS)
        self._event_types = {e.strip() for e in events_raw.split(",") if e.strip()}

        for event_type in self._event_types:
            _bus.subscribe(event_type, self._on_event)

        logger.info(
            "WebhookNotifier active: events=%s → %s",
            sorted(self._event_types),
            self.url,
        )

    def _on_event(self, data: dict) -> None:
        threading.Thread(
            target=self._post,
            args=(dict(data),),
            daemon=True,
            name="pathly-webhook",
        ).start()

    def _post(self, data: dict) -> None:
        try:
            payload = json.dumps(data, default=str).encode("utf-8")
            req = urllib.request.Request(
                self.url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent":   "pathly-webhook/1.0",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.debug(
                    "Webhook posted %s → HTTP %d", data.get("type"), resp.status
                )
        except urllib.error.HTTPError as exc:
            logger.warning(
                "Webhook HTTP %d for %s: %s", exc.code, data.get("type"), exc.reason
            )
        except Exception as exc:
            logger.warning("Webhook send failed for %s: %s", data.get("type"), exc)


_notifier = WebhookNotifier()
