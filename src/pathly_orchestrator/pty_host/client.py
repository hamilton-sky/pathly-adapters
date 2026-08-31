"""The two callbacks a spawn host owes the FSM server.

``/runner/terminal/started`` releases the supervisor's 30s spawn wait;
``/runner/terminal/result`` is the authoritative, run-keyed billing gate — the one
chokepoint every runner spawn passes through — so it must carry the spawn-time adapter and
the raw stdout the server re-parses. Both mirror what ``studio/src/main/ipc/terminal/``
posts, because the server cannot tell the two hosts apart and must not have to.
"""

from __future__ import annotations

import logging

from pathly_orchestrator.fsm_http_client import _request_json

logger = logging.getLogger("pathly.pty_host")

_RESULT_TIMEOUT = 30.0


def post_started(
    *, host: str, port: int, tab_id: str, run_id: str, topic: str, pid: int
) -> bool:
    try:
        _request_json(
            "POST",
            "/runner/terminal/started",
            {"tab_id": tab_id, "run_id": run_id, "topic": topic, "pid": pid},
            host=host,
            port=port,
        )
        return True
    except Exception as exc:
        logger.error(
            "pty_host: /runner/terminal/started failed for %s: %s", tab_id, exc
        )
        return False


def post_result(
    *,
    host: str,
    port: int,
    run_id: str,
    topic: str,
    adapter: str,
    exit_code: int,
    stdout_tail: str,
    wall_seconds: float,
    user_initiated: bool,
) -> bool:
    """Report a finished spawn. Retried once — losing this hangs the run for 30 minutes."""
    payload = {
        "run_id": run_id,
        "topic": topic,
        "adapter": adapter,
        "exit_code": exit_code,
        "stdout_tail": stdout_tail,
        "wall_seconds": wall_seconds,
        "user_initiated": user_initiated,
    }
    for attempt in (1, 2):
        try:
            _request_json(
                "POST",
                "/runner/terminal/result",
                payload,
                host=host,
                port=port,
                timeout=_RESULT_TIMEOUT,
            )
            return True
        except Exception as exc:
            logger.error(
                "pty_host: /runner/terminal/result attempt %d failed for run %s: %s",
                attempt,
                run_id,
                exc,
            )
    return False
