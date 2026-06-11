"""Centralized server configuration loaded from environment variables."""

from __future__ import annotations

import os
import secrets as _secrets_mod
import sys
from dataclasses import dataclass


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

        return cls(
            host=os.environ.get("PATHLY_FSM_HTTP_HOST", "127.0.0.1"),
            port=port,
            cors_origin=os.environ.get("PATHLY_CORS_ORIGIN", "*"),
            api_secret=os.environ.get("PATHLY_API_SECRET") or _load_or_create_secret(),
            project_root=os.environ.get("PATHLY_PROJECT_ROOT", ""),
            rate_limit_max=int(os.environ.get("PATHLY_RATE_LIMIT_MAX", "120")),
            rate_limit_window=int(os.environ.get("PATHLY_RATE_LIMIT_WINDOW", "60")),
            log_level=os.environ.get("PATHLY_LOG_LEVEL", "INFO").upper(),
        )
