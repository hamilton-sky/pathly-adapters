"""Minimal SSE reader over urllib — no third-party HTTP dependency.

The FSM server's ``/events/*`` streams are plain ``text/event-stream``: ``data: <json>``
lines, blank-line-separated, with ``: keepalive`` comments every 25s. That is little
enough protocol to read directly, and this package must not add a dependency the rest of
the orchestrator does not already have.
"""

from __future__ import annotations

import json
import logging
import socket
from typing import Callable, Iterator
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger("pathly.pty_host")


def iter_events(
    url: str,
    *,
    timeout: float = 60.0,
    on_open: Callable[[object], None] | None = None,
) -> Iterator[dict]:
    """Yield decoded ``data:`` payloads from one SSE connection.

    Returns normally when the stream closes; raises :class:`ConnectionError` on connect
    failure so the caller can apply its own reconnect policy. ``/events/*`` is exempt from
    the server's API-secret check, so no auth header is needed here.

    ``on_open`` receives the live response so a caller can close it from another thread.
    A blocking read on an idle stream is otherwise uninterruptible until the next keepalive,
    which turns every shutdown into a stall.
    """
    req = Request(url, headers={"Accept": "text/event-stream"})
    try:
        response = urlopen(req, timeout=timeout)  # nosec B310 — loopback FSM server
    except (HTTPError, URLError, TimeoutError) as exc:
        raise ConnectionError(f"SSE connect failed for {url}: {exc}") from exc

    if on_open is not None:
        on_open(response)

    try:
        for raw_line in response:
            payload = _decode_line(raw_line)
            if payload is not None:
                yield payload
    except (OSError, ValueError, AttributeError):
        # The response was closed under us — a deliberate shutdown, not a fault. Closing an
        # http.client response mid-read drops its socket file object, so the in-flight
        # readline surfaces as AttributeError ('NoneType' has no 'peek') rather than OSError;
        # all three mean the same thing here. Ending the iteration lets the caller's
        # reconnect/stop logic decide what happens next.
        return
    finally:
        try:
            response.close()
        except OSError:
            pass


def _decode_line(raw_line: bytes) -> dict | None:
    """One wire line → an event payload, or None for framing/keepalive/garbage."""
    line = raw_line.decode("utf-8", "replace").strip()
    if not line or line.startswith(":"):
        return None  # blank separator or keepalive comment
    if not line.startswith("data:"):
        return None
    body = line[len("data:") :].strip()
    if not body:
        return None
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.warning("pty_host: undecodable SSE payload: %.120s", body)
        return None
    return payload if isinstance(payload, dict) else None


def close_stream(response: object) -> None:
    """Interrupt a blocked read on `response` from another thread.

    Calling ``close()`` here would DEADLOCK-BY-WAITING: it needs the BufferedReader lock
    that the blocked ``readline()`` already holds, so it only returns once that read does —
    which on an idle SSE stream means the server's next 25s keepalive, turning every
    shutdown into a 25s stall. ``socket.shutdown()`` reaches past the buffer and makes the
    in-flight ``recv()`` return EOF immediately; the reader's own ``finally`` then closes
    the response normally.
    """
    sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass  # already closed or never connected — the reader ends either way
