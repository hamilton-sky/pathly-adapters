"""The plaintext hook secrets of open claude chiefs, held in memory and handed on once.

No file holds a chief's hook secret (chief-autopilot-round-two 15). ``open_chief`` generates it,
stores only its sha256 in the session row and ``offer``s the plaintext here. Studio's main process
``claim``s it once (``POST /chief/hook-secret``) and puts it in the chief claude's environment,
where the ``UserPromptSubmit`` hook reads it. A claim that finds nothing to hand on means the
secret was taken already (or was never offered), so it closes the chief (ticket 13, question 2 =
A): whoever took it first no longer holds a working secret. ``close_chief`` calls ``forget``.

The secrets live in this process only: a restart loses them, and ``chief_startup_cleanup`` closes
every session the last process left open.
"""

from __future__ import annotations

import threading

SECOND_CLAIM = "hook secret claimed twice"

_lock = threading.Lock()
_offered: dict[str, str] = {}


def offer(run_id: str, secret: str) -> None:
    """Hold ``secret`` for ``run_id`` until it is claimed or the chief closes."""
    with _lock:
        _offered[run_id] = secret


def claim(run_id: str) -> str | None:
    """The secret, once; it is forgotten as it is handed on.

    Any later call returns None and closes the chief (``close_chief(run_id, SECOND_CLAIM)``,
    harmless for a session that is closed or unknown). The lock is not held across the close,
    which calls ``forget``.
    """
    with _lock:
        secret = _offered.pop(run_id, None)
    if secret is not None:
        return secret
    from .chief_session import close_chief

    close_chief(run_id, SECOND_CLAIM)
    return None


def forget(run_id: str) -> None:
    """Drop the secret of ``run_id`` if it was never claimed."""
    with _lock:
        _offered.pop(run_id, None)
