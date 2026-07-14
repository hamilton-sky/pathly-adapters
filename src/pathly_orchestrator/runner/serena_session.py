"""Minimal Serena MCP session — a long-lived subprocess + JSON-RPC stdio client.

Transport layer for the ``lsp`` code-intelligence backend
(:mod:`.code_context_lsp`). Serena is an MCP **server** (not a one-shot CLI), so
this runs it as a subprocess and speaks the minimal JSON-RPC it needs:
``initialize`` handshake → ``notifications/initialized`` → ``tools/call``. A
background reader thread parses newline-delimited JSON-RPC off stdout into
per-request-id queues; callers wait on those with a deadline, so a wedged server
can never block the prompt. ``call_tool`` never raises — it returns ``None`` on
any failure. Owns exactly one concern: talk to a Serena process.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import threading

# Serena launch argv — mirrors src/pathly_data/adapters/*/_mcp/serena.json (the
# repo's known-good invocation). ``start()`` appends ``--project <root>`` so any
# project path activates (creating ``.serena/`` config on first use) — more robust
# than ``--project-from-cwd``, which only works once a ``.serena/project.yml``
# already exists. Overridable via PATHLY_SERENA_ARGV (a JSON array); an override
# that already carries a ``--project``/``--project-from-cwd`` flag is respected.
_DEFAULT_SERENA_ARGV = [
    "uvx",
    "--from",
    "git+https://github.com/oraios/serena",
    "serena",
    "start-mcp-server",
    "--context",
    "claude-code",  # current name (ide-assistant is deprecated → claude-code)
    "--enable-web-dashboard",
    "false",  # don't spawn a dashboard HTTP server inside the FSM host per session
]

_QUERY_TIMEOUT_S = 8  # per tool call, once the session is ready
_BOOT_TIMEOUT_S = 180  # cold LSP boot budget (async — never blocks a request)


def serena_argv() -> list[str]:
    """The Serena launch argv, honoring the PATHLY_SERENA_ARGV override."""
    raw = os.environ.get("PATHLY_SERENA_ARGV", "").strip()
    if raw:
        try:
            argv = json.loads(raw)
            if (
                isinstance(argv, list)
                and argv
                and all(isinstance(a, str) for a in argv)
            ):
                return argv
        except ValueError:
            pass
    return list(_DEFAULT_SERENA_ARGV)


class SerenaSession:
    """One long-lived Serena MCP subprocess + a minimal JSON-RPC stdio client."""

    def __init__(self, root: str) -> None:
        self.root = root
        self._proc: subprocess.Popen | None = None
        self._id = 0
        self._id_lock = threading.Lock()
        self._responses: dict[int, queue.Queue] = {}
        self._resp_lock = threading.Lock()
        self.ready = False

    # -- lifecycle --------------------------------------------------------
    def start(self) -> bool:
        """Spawn Serena, do the MCP handshake, mark ready. Returns success."""
        argv = serena_argv()
        exe = shutil.which(argv[0])
        if not exe:
            return False  # launcher (uvx) not installed → safe no-op
        full = [exe, *argv[1:]]
        if "--project" not in argv and "--project-from-cwd" not in argv:
            full += ["--project", self.root]  # activate this exact path
        try:
            self._proc = subprocess.Popen(
                full,
                cwd=self.root,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,  # Serena logs to stderr; keep stdout JSON-only
                text=True,
                bufsize=1,
            )
        except (OSError, ValueError):
            return False
        threading.Thread(target=self._reader, daemon=True).start()
        init = self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pathly-code-proxy", "version": "1.0.0"},
            },
            timeout=_BOOT_TIMEOUT_S,
        )
        if init is None:
            self.close()
            return False
        self._notify("notifications/initialized", {})
        self.ready = True
        return True

    def close(self) -> None:
        self.ready = False
        proc, self._proc = self._proc, None
        if proc is not None:
            try:
                proc.terminate()
            except Exception:
                pass

    # -- io ---------------------------------------------------------------
    def _reader(self) -> None:
        """Parse JSON-RPC lines off stdout into the waiting per-id queues."""
        proc = self._proc
        if proc is None or proc.stdout is None:
            return
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # non-JSON log noise on stdout — ignore
            if not isinstance(msg, dict) or "id" not in msg:
                continue  # a notification / non-response
            with self._resp_lock:
                q = self._responses.get(msg.get("id"))
            if q is not None:
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass

    def _next_id(self) -> int:
        with self._id_lock:
            self._id += 1
            return self._id

    def _send(self, obj: dict) -> bool:
        proc = self._proc
        if proc is None or proc.stdin is None:
            return False
        try:
            proc.stdin.write(json.dumps(obj) + "\n")
            proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def _notify(self, method: str, params: dict) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict, timeout: float):
        """Send a request and wait up to ``timeout`` for its result, or ``None``."""
        mid = self._next_id()
        q: queue.Queue = queue.Queue(maxsize=1)
        with self._resp_lock:
            self._responses[mid] = q
        try:
            if not self._send(
                {"jsonrpc": "2.0", "id": mid, "method": method, "params": params}
            ):
                return None
            try:
                msg = q.get(timeout=timeout)
            except queue.Empty:
                return None
            return msg.get("result") if isinstance(msg, dict) else None
        finally:
            with self._resp_lock:
                self._responses.pop(mid, None)

    # -- tools ------------------------------------------------------------
    def call_tool(self, name: str, arguments: dict):
        """Call an MCP tool; return its text content, or ``None`` on failure."""
        if not self.ready:
            return None
        result = self._request(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=_QUERY_TIMEOUT_S,
        )
        if not isinstance(result, dict):
            return None
        content = result.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    return item.get("text")
        return None
