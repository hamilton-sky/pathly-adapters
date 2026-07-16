"""HTTP client for the Pathly FSM server.

CLI argument parsing and the `main()` entry point live in fsm_cli.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

_SERVER_MODULE = "pathly_orchestrator.http_server"
_HEALTH_PATH = "/health"
_NEXT_ACTION_PATH = "/next_action"
_COMPLETE_STAGE_PATH = "/complete_stage"
_RECORD_ACTIVITY_PATH = "/record_activity"
_RECORD_PHASE_PATH = "/record_phase"
_CODE_QUERY_PATH = "/code/query"

# Prompt assembly inside /next_action + /complete_stage (skill compose + board-context retrieval +
# code-context injection, which can trigger a codebase-memory-mcp re-index after a code edit)
# legitimately takes many seconds. The old 10s default timed out on a heavy /next_action and, because
# a socket TimeoutError isn't a RuntimeError, crashed the supervisor loop (loop_crashed). Give the two
# heavy FSM calls a generous ceiling; on timeout they still degrade to the in-process path below.
_FSM_CALL_TIMEOUT = 120.0


class _ServerUnreachable(RuntimeError):
    """The FSM HTTP server can't be reached or started. Callers degrade to running
    fsm_ops in-process so the pipeline keeps moving when the server is down. (A real
    HTTP error response — 4xx/5xx — is NOT this; it surfaces normally.)"""


def _base_url(host: str, port: int) -> str:
    return f"http://{host}:{port}"


def _load_secret() -> str:
    """Read the shared API secret the server authenticates against.

    Mirrors the server's resolution order (``PATHLY_API_SECRET`` env, then
    ``~/.pathly/server_secret.txt``) but never creates the file — a missing
    secret simply means no header is sent, which is correct for an unsecured
    server.
    """
    env = os.environ.get("PATHLY_API_SECRET")
    if env:
        return env.strip()
    secret_file = Path.home() / ".pathly" / "server_secret.txt"
    try:
        return secret_file.read_text().strip()
    except OSError:
        return ""


def _request_raw(
    method: str,
    path: str,
    payload: dict | None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
) -> str:
    url = _base_url(host, port) + path
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    secret = _load_secret()
    if secret:
        headers["X-Pathly-Secret"] = secret
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:  # nosec B310
            return resp.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        detail = body or exc.reason
        raise RuntimeError(f"fsm-call error ({exc.code}): {detail}") from exc
    except (TimeoutError, URLError) as exc:
        # A socket read/connect timeout raises a raw TimeoutError (NOT wrapped in URLError) — e.g. the
        # supervisor's self-call to /next_action outlasting `timeout` because prompt assembly is slow.
        # Treat timeout AND unreachable identically: degrade to the in-process fsm_ops path instead of
        # letting the exception bubble to the supervisor loop's catch-all and become loop_crashed.
        reason = getattr(exc, "reason", None) or "request timed out"
        raise _ServerUnreachable(f"fsm-call: server not answering: {reason}") from exc


def _request_json(
    method: str,
    path: str,
    payload: dict | None,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 10.0,
) -> dict:
    raw = _request_raw(method, path, payload, host=host, port=port, timeout=timeout)
    if not raw.strip():
        return {}
    return json.loads(raw)


def _health_ok(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> bool:
    try:
        payload = _request_json(
            "GET", _HEALTH_PATH, None, host=host, port=port, timeout=1.0
        )
    except Exception:
        return False
    return payload.get("status") == "ok"


def _pid_file() -> Path:
    try:
        import platformdirs

        cache_dir = Path(platformdirs.user_cache_dir("pathly"))
    except ImportError:
        cache_dir = Path.home() / ".cache" / "pathly"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "fsm.pid"


def _start_server(*, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    pid_path = _pid_file()
    if pid_path.exists():
        try:
            int(pid_path.read_text().strip())  # validate PID is parseable
            if _health_ok(host=host, port=port):
                return
        except (ValueError, OSError):
            pass
        pid_path.unlink(missing_ok=True)

    try:
        kwargs: dict = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        if os.name == "nt":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS  # type: ignore[attr-defined]
            )
        else:
            kwargs["start_new_session"] = True

        proc = subprocess.Popen(
            [sys.executable, "-m", _SERVER_MODULE],
            **kwargs,
        )
        pid_path.write_text(str(proc.pid))
    except OSError as exc:
        raise _ServerUnreachable(
            "FSM server unavailable. Start it with:\n"
            "  pathly-fsm-http\n"
            "(Run in a separate terminal, then retry.)"
        ) from exc


def ensure_server_running(
    *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
) -> None:
    if _health_ok(host=host, port=port):
        return

    _start_server(host=host, port=port)
    for _ in range(30):
        if _health_ok(host=host, port=port):
            return
        time.sleep(0.25)

    raise _ServerUnreachable(
        "FSM server did not start within 7.5 s — run `pathly-fsm-http` to diagnose."
    )


def _inprocess(fn_name: str, payload: dict) -> dict:
    """Graceful degradation: run the FSM in-process via fsm_ops when the HTTP
    server is unreachable. fsm_ops reads the fsm_state DB and falls back to the
    STATE.json mirror, so next-action / complete-stage still work with no server."""
    from pathly_orchestrator import fsm_ops

    return getattr(fsm_ops, fn_name)(payload)


def next_action(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    try:
        ensure_server_running(host=host, port=port)
        return _request_json(
            "POST",
            _NEXT_ACTION_PATH,
            payload,
            host=host,
            port=port,
            timeout=_FSM_CALL_TIMEOUT,
        )
    except _ServerUnreachable:
        return _inprocess("next_action", payload)


def complete_stage(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    try:
        ensure_server_running(host=host, port=port)
        return _request_json(
            "POST",
            _COMPLETE_STAGE_PATH,
            payload,
            host=host,
            port=port,
            timeout=_FSM_CALL_TIMEOUT,
        )
    except _ServerUnreachable:
        return _inprocess("complete_stage", payload)


def record_activity(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    trace_id: str = "",
    span_id: str = "",
) -> dict:
    ensure_server_running(host=host, port=port)
    if trace_id or span_id:
        payload = dict(payload)
        if trace_id:
            payload["trace_id"] = trace_id
        if span_id:
            payload["span_id"] = span_id
    return _request_json("POST", _RECORD_ACTIVITY_PATH, payload, host=host, port=port)


def record_phase(
    payload: dict,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
) -> dict:
    ensure_server_running(host=host, port=port)
    return _request_json("POST", _RECORD_PHASE_PATH, payload, host=host, port=port)


def _filter_none(values: dict[str, object | None]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value is not None}


# Backward-compat: expose `main` for any external caller that does
# `from pathly_orchestrator.fsm_http_client import main`. Resolved lazily via a
# PEP 562 module __getattr__ so importing this module NEVER imports fsm_cli at
# load time. fsm_cli imports this module at its top (line 13), so a load-time
# re-export here is an import cycle: it breaks whenever fsm_cli is imported
# first — exactly what the `pathly-fsm-call` console script (fsm_cli:main) does.
# Deferring to attribute access keeps the re-export working without the cycle.
def __getattr__(name: str):
    if name == "main":
        from pathly_orchestrator.fsm_cli import main as _main

        return _main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
