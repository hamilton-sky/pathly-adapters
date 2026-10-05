"""Headless spawn host — the piece that lets a run drain without Studio.

The supervisor never spawns a CLI itself. It emits a ``TERMINAL_SPAWN`` event on the
server's topic-independent ``/events/spawn`` stream and blocks for 30s waiting for
*somebody* to answer with ``POST /runner/terminal/started``. Until now the only somebody
was Studio's Electron main process, so "headless" meant "no human in the per-step loop"
but still required a desktop app to be running — no CI, no server-side drain.

This host answers the same three events (``TERMINAL_SPAWN`` / ``TERMINAL_KILL`` /
``TERMINAL_SIGNAL``) with the same two callbacks, so the supervisor cannot tell which host
it is talking to and needed no change. Run it beside ``pathly-fsm-http``:

    pathly-fsm-http &
    pathly-pty-host

Only ONE host should subscribe at a time — both would spawn the same run twice.
"""

from __future__ import annotations

import logging
import os
import threading
from collections import deque

from . import client
from .process import SpawnedProcess
from .sse import close_stream, iter_events

logger = logging.getLogger("pathly.pty_host")

_SPAWN_PATH = "/events/spawn"
_RECONNECT_MIN = 1.0
_RECONNECT_MAX = 30.0
DEFAULT_MAX_CONCURRENT = 5

# How many recent tab_ids to remember for redelivery suppression. A reconnect replays at
# most the events in flight, so recent history is all that can repeat — and a host that
# drains for weeks must not accumulate one string per stage forever.
_CLAIM_MEMORY = 2048


class SpawnHost:
    """Subscribes to the spawn stream and runs what it is told to run."""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8765,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT,
    ) -> None:
        self._host = host
        self._port = port
        self._slots = threading.Semaphore(max_concurrent)
        self._max_concurrent = max_concurrent
        self._active: dict[str, SpawnedProcess] = {}
        self._claimed: deque[str] = deque(maxlen=_CLAIM_MEMORY)
        self._claimed_index: set[str] = set()
        self._stream: object | None = None
        self._lock = threading.Lock()
        self._stopping = threading.Event()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Consume the spawn stream until stopped, reconnecting with backoff."""
        url = f"http://{self._host}:{self._port}{_SPAWN_PATH}"
        backoff = _RECONNECT_MIN
        logger.info(
            "pty_host: listening on %s (max %d concurrent)", url, self._max_concurrent
        )
        while not self._stopping.is_set():
            try:
                for event in iter_events(url, on_open=self._hold_stream):
                    if self._stopping.is_set():
                        return
                    backoff = (
                        _RECONNECT_MIN  # a delivered event proves the link is good
                    )
                    self._dispatch(event)
            except ConnectionError as exc:
                logger.warning("pty_host: %s — retrying in %.0fs", exc, backoff)
            except Exception:
                logger.exception(
                    "pty_host: spawn stream error — retrying in %.0fs", backoff
                )
            if self._stopping.wait(backoff):
                return
            backoff = min(backoff * 2, _RECONNECT_MAX)

    def stop(self) -> None:
        """Stop listening and kill every child, so no CLI outlives the host."""
        self._stopping.set()
        self._close_stream()
        with self._lock:
            running = list(self._active.values())
        for proc in running:
            proc.terminate()

    def _hold_stream(self, response: object) -> None:
        """Keep the live SSE response so stop() can unblock a read from another thread."""
        with self._lock:
            self._stream = response
        if self._stopping.is_set():
            self._close_stream()  # stopped mid-connect — do not settle into a blocked read

    def _close_stream(self) -> None:
        with self._lock:
            stream = self._stream
            self._stream = None
        if stream is not None:
            close_stream(stream)

    # ── event dispatch ────────────────────────────────────────────────────────

    def _dispatch(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "TERMINAL_SPAWN":
            self._on_spawn(event)
        elif kind == "TERMINAL_KILL":
            self._on_kill(str(event.get("tab_id") or ""))
        elif kind == "TERMINAL_SIGNAL" and event.get("signal") == "term":
            self._on_kill(str(event.get("tab_id") or ""))

    def _on_spawn(self, event: dict) -> None:
        tab_id = str(event.get("tab_id") or "")
        argv = event.get("argv")
        if not tab_id or not isinstance(argv, list) or not argv:
            logger.error("pty_host: unusable TERMINAL_SPAWN (tab_id=%r)", tab_id)
            return

        with self._lock:
            if tab_id in self._claimed_index:
                return  # idempotent — a reconnect can redeliver, never double-spawn
            if len(self._claimed) == self._claimed.maxlen:
                self._claimed_index.discard(self._claimed[0])
            self._claimed.append(tab_id)
            self._claimed_index.add(tab_id)

        if event.get("interactive"):
            # An interactive REPL needs a terminal and a human; headless has neither.
            # Report a clean failure instead of letting the supervisor wait out its
            # 30-minute result timeout on a stage that can never complete here.
            self._report_unrunnable(
                event,
                "pty_host cannot run an INTERACTIVE stage: no terminal and no human. "
                "Run this stage under Studio, or configure the flow for headless.",
            )
            return

        threading.Thread(
            target=self._run_spawn,
            args=(event, tab_id, [str(a) for a in argv]),
            daemon=True,
            name=f"pty-host-{tab_id}",
        ).start()

    def _on_kill(self, tab_id: str) -> None:
        if not tab_id:
            return
        with self._lock:
            proc = self._active.get(tab_id)
        if proc is None:
            return
        logger.info("pty_host: killing %s (pid %s) on request", tab_id, proc.pid)
        proc.terminate()

    # ── the spawn itself ──────────────────────────────────────────────────────

    def _run_spawn(self, event: dict, tab_id: str, argv: list[str]) -> None:
        self._slots.acquire()
        proc = None
        try:
            proc = self._start(event, tab_id, argv)
            if proc is None:
                return
            exit_code = proc.wait()
            logger.info("pty_host: %s exited %s", tab_id, exit_code)
            self._report(
                event,
                exit_code=exit_code,
                stdout_tail=proc.tail.text(),
                wall_seconds=proc.wall_seconds(),
                user_initiated=proc.killed_by_host,
            )
        finally:
            with self._lock:
                self._active.pop(tab_id, None)
            self._slots.release()

    def _start(
        self, event: dict, tab_id: str, argv: list[str]
    ) -> SpawnedProcess | None:
        cwd = str(event.get("cwd") or os.getcwd())
        try:
            proc = SpawnedProcess(argv, cwd, self._child_env(cwd))
        except OSError as exc:
            logger.error("pty_host: spawn failed for %s (%s): %s", tab_id, argv[0], exc)
            self._report_unrunnable(
                event, f"pty_host could not spawn {argv[0]!r}: {exc}"
            )
            return None

        with self._lock:
            self._active[tab_id] = proc
        logger.info("pty_host: spawned %s → pid %s (%s)", tab_id, proc.pid, argv[0])

        client.post_started(
            host=self._host,
            port=self._port,
            tab_id=tab_id,
            run_id=str(event.get("run_id") or ""),
            topic=str(event.get("topic") or ""),
            pid=proc.pid,
        )
        return proc

    @staticmethod
    def _child_env(cwd: str) -> dict[str, str]:
        # PATHLY_GATE_BILLED marks this as a gate-billed runner spawn so the interactive
        # stop hook skips it — without it the hook double-bills and mis-attributes via its
        # "most recently active feature" guess. PATHLY_PROJECT_ROOT matches what Studio
        # exports on every child.
        return {
            **os.environ,
            "PATHLY_PROJECT_ROOT": cwd,
            "PATHLY_GATE_BILLED": "1",
        }

    # ── result reporting ──────────────────────────────────────────────────────

    def _report_unrunnable(self, event: dict, reason: str) -> None:
        logger.error("pty_host: %s", reason)
        self._report(
            event,
            exit_code=1,
            stdout_tail=reason,
            wall_seconds=0.0,
            user_initiated=False,
        )

    def _report(
        self,
        event: dict,
        *,
        exit_code: int,
        stdout_tail: str,
        wall_seconds: float,
        user_initiated: bool,
    ) -> None:
        client.post_result(
            host=self._host,
            port=self._port,
            run_id=str(event.get("run_id") or ""),
            topic=str(event.get("topic") or ""),
            # The spawn-time adapter, straight from the event. Studio re-derives it from
            # argv[0] only because its Windows argv is a PowerShell wrapper; here the
            # server's own value is both available and authoritative.
            adapter=str(event.get("adapter") or "").strip().lower(),
            exit_code=exit_code,
            stdout_tail=stdout_tail,
            wall_seconds=wall_seconds,
            user_initiated=user_initiated,
        )


def run_host(
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    max_concurrent: int = DEFAULT_MAX_CONCURRENT,
) -> SpawnHost:
    """Build a host and run it in the CURRENT thread until stopped."""
    spawn_host = SpawnHost(host=host, port=port, max_concurrent=max_concurrent)
    spawn_host.run()
    return spawn_host


__all__ = ["SpawnHost", "run_host", "DEFAULT_MAX_CONCURRENT"]
