"""Headless spawn host — runs a Pathly pipeline's CLI agents without Studio.

``supervisor/terminal.py`` emits ``TERMINAL_SPAWN`` on the server's ``/events/spawn``
stream and waits for a host to answer. Studio's Electron main process is one such host;
this package is the other, so a run can drain on a server or in CI. See ``host.py`` for
the contract.
"""

from __future__ import annotations

from .host import DEFAULT_MAX_CONCURRENT, SpawnHost, run_host

__all__ = ["SpawnHost", "run_host", "DEFAULT_MAX_CONCURRENT"]
