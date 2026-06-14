"""Centralized server configuration loaded from environment variables."""

from __future__ import annotations

import os
import secrets as _secrets_mod
import sys
from dataclasses import dataclass

# Addresses that are guaranteed loopback — binding to these never exposes
# the server beyond the current user's machine.
_LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "::1", "localhost"})


def _load_or_create_secret() -> str:
    """Read the shared API secret from ~/.pathly/server_secret.txt, creating it if absent."""
    from pathlib import Path
    secret_file = Path.home() / ".pathly" / "server_secret.txt"
    secret_file.parent.mkdir(parents=True, exist_ok=True)
    if secret_file.exists():
        val = secret_file.read_text().strip()
        if val:
            return val
    val = _secrets_mod.token_hex(32)
    secret_file.write_text(val)
    return val


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    cors_origin: str
    api_secret: str
    project_root: str
    rate_limit_max: int
    rate_limit_window: int
    log_level: str

    @classmethod
    def from_env(cls) -> "Settings":
        port_str = os.environ.get("PATHLY_FSM_HTTP_PORT", "8765")
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError()
        except ValueError:
            print(
                f"ERROR: PATHLY_FSM_HTTP_PORT must be 1-65535, got {port_str!r}",
                file=sys.stderr,
            )
            sys.exit(1)

        host = os.environ.get("PATHLY_FSM_HTTP_HOST", "127.0.0.1")
        if host not in _LOOPBACK_HOSTS:
            expose = os.environ.get("PATHLY_EXPOSE_HOST", "").strip().lower() == "true"
            if not expose:
                print(
                    f"ERROR: PATHLY_FSM_HTTP_HOST={host!r} is a non-loopback address.\n"
                    "Binding to a non-loopback interface exposes the FSM server and its\n"
                    "unauthenticated SSE streams (/events/*) on the network.\n"
                    "If you intentionally want this, set PATHLY_EXPOSE_HOST=true.\n"
                    "See docs/SECURITY.md for the trust model.",
                    file=sys.stderr,
                )
                sys.exit(1)
            print(
                f"WARNING: PATHLY_FSM_HTTP_HOST={host!r} — FSM server will bind on a\n"
                "non-loopback interface. The /events/* SSE streams have NO authentication\n"
                "and will be reachable by anyone who can reach this address.\n"
                "Set PATHLY_FSM_HTTP_HOST=127.0.0.1 to restrict to localhost only.",
                file=sys.stderr,
            )

        return cls(
            host=host,
            port=port,
            cors_origin=os.environ.get("PATHLY_CORS_ORIGIN", "*"),
            api_secret=os.environ.get("PATHLY_API_SECRET") or _load_or_create_secret(),
            project_root=os.environ.get("PATHLY_PROJECT_ROOT", ""),
            rate_limit_max=int(os.environ.get("PATHLY_RATE_LIMIT_MAX", "120")),
            rate_limit_window=int(os.environ.get("PATHLY_RATE_LIMIT_WINDOW", "60")),
            log_level=os.environ.get("PATHLY_LOG_LEVEL", "INFO").upper(),
        )
