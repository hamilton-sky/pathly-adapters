"""One spawned CLI process: run it, capture its output, kill its whole tree.

Studio spawns each stage into a node-pty pseudo-terminal because a human watches the tab.
Headless there is nobody to watch, so this uses ordinary pipes — every adapter's headless
mode (``claude -p``, ``codex exec``) is non-interactive by construction and needs no TTY.

Two details are load-bearing rather than incidental:

* **stdin is /dev/null.** ``codex`` headless stalls waiting on terminal input otherwise —
  the same hazard ``terminal.ts`` handles by piping ``$null`` on Windows.
* **The child gets its own process group** (POSIX) or group flag (Windows), so a kill
  reaches the CLI's own children. Killing only the direct child is what leaves orphaned
  CLI processes behind after an abort.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from collections import deque

logger = logging.getLogger("pathly.pty_host")

_DEFAULT_TAIL_BYTES = 4 * 1024 * 1024
_TERM_GRACE_SECONDS = 5.0


class OutputTail:
    """A rolling byte-bounded tail of the child's combined output.

    The server re-parses this with ``runner/output.py::parse_result``, which can recover a
    truncated claude envelope — but recovery is a fallback, not a plan. The cap here is
    ~8000x Studio's rolling chunk buffer, so a real run is kept whole and only a runaway
    is clipped.
    """

    def __init__(self, max_bytes: int = _DEFAULT_TAIL_BYTES) -> None:
        self._max_bytes = max_bytes
        self._chunks: deque[str] = deque()
        self._size = 0
        self._lock = threading.Lock()

    def append(self, chunk: str) -> None:
        if not chunk:
            return
        with self._lock:
            self._chunks.append(chunk)
            self._size += len(chunk)
            while self._size > self._max_bytes and len(self._chunks) > 1:
                self._size -= len(self._chunks.popleft())

    def text(self) -> str:
        with self._lock:
            return "".join(self._chunks)


class SpawnedProcess:
    """A running CLI, its captured output, and the means to stop it."""

    def __init__(self, argv: list[str], cwd: str, env: dict[str, str]) -> None:
        self.argv = argv
        self.cwd = cwd
        self.tail = OutputTail()
        self.started_at = time.monotonic()
        self.killed_by_host = False
        self._proc = subprocess.Popen(  # nosec B603 — argv comes from the FSM server
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            **_process_group_kwargs(),
        )
        self._reader = threading.Thread(
            target=self._drain, daemon=True, name=f"pty-host-read-{self._proc.pid}"
        )
        self._reader.start()

    @property
    def pid(self) -> int:
        return self._proc.pid

    def _drain(self) -> None:
        stream = self._proc.stdout
        if stream is None:
            return
        try:
            for line in stream:
                self.tail.append(line)
        except (OSError, ValueError):
            pass  # stream closed under us by a kill — the exit code is the real signal

    def wait(self) -> int:
        exit_code = self._proc.wait()
        self._reader.join(timeout=5)
        return exit_code

    def wall_seconds(self) -> float:
        return time.monotonic() - self.started_at

    def terminate(self) -> None:
        """Stop the child and everything it spawned. Escalates TERM → KILL."""
        self.killed_by_host = True
        if self._proc.poll() is not None:
            return
        self._signal_tree(signal.SIGTERM)
        deadline = time.monotonic() + _TERM_GRACE_SECONDS
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                return
            time.sleep(0.1)
        self._signal_tree(signal.SIGKILL)

    def _signal_tree(self, sig: int) -> None:
        try:
            if os.name == "nt":
                # No process groups to signal portably; taskkill /T walks the tree.
                subprocess.run(  # nosec B603 B607 — fixed argv, pid from our own child
                    ["taskkill", "/PID", str(self._proc.pid), "/T", "/F"],
                    capture_output=True,
                    timeout=15,
                )
            else:
                os.killpg(os.getpgid(self._proc.pid), sig)
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug("pty_host: signalling %s failed: %s", self._proc.pid, exc)
            try:
                self._proc.kill()
            except OSError:
                pass


def _process_group_kwargs() -> dict:
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}
