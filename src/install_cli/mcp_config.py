"""Write / remove MCP server config for pathly-telemetry in host config files.

- Claude Code: ~/.claude/settings.json  (JSON, mcpServers key)
- Codex:       ~/.codex/config.toml     (TOML, [mcp_servers.X] section)
- Copilot:     not supported (no MCP config convention yet)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SERVER_NAME = "pathly-telemetry"

_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
_CODEX_CONFIG = Path.home() / ".codex" / "config.toml"

# The MCP server is run via  python -m pathly_telemetry
_CLAUDE_ENTRY: dict = {
    "command": "python",
    "args": ["-m", "pathly_telemetry"],
}

_CODEX_TOML_BLOCK = (
    f"\n[mcp_servers.{_SERVER_NAME}]\n"
    'command = "python"\n'
    'args = ["-m", "pathly_telemetry"]\n'
)


# ── public API ────────────────────────────────────────────────────────────────


def install_mcp_config(host: str, *, dry_run: bool = False) -> None:
    """Register pathly-telemetry MCP server in the host config file."""
    if host == "claude":
        _install_claude(dry_run=dry_run)
    elif host == "codex":
        _install_codex(dry_run=dry_run)
    # copilot: no MCP config convention yet — skip silently


def uninstall_mcp_config(host: str, *, dry_run: bool = False) -> None:
    """Remove pathly-telemetry MCP server entry from the host config file."""
    if host == "claude":
        _uninstall_claude(dry_run=dry_run)
    elif host == "codex":
        _uninstall_codex(dry_run=dry_run)


# ── Claude ────────────────────────────────────────────────────────────────────


def _install_claude(*, dry_run: bool) -> None:
    path = _CLAUDE_SETTINGS
    cfg = _read_json(path)
    if cfg is None:
        return

    servers: dict = cfg.setdefault("mcpServers", {})
    if _SERVER_NAME in servers:
        return  # already registered

    if dry_run:
        print(f"  [dry-run] Would add MCP server '{_SERVER_NAME}' to {path}")
        return

    servers[_SERVER_NAME] = _CLAUDE_ENTRY
    _write_json(path, cfg)
    print(f"[claude] Registered MCP server '{_SERVER_NAME}' in settings.json")


def _uninstall_claude(*, dry_run: bool) -> None:
    path = _CLAUDE_SETTINGS
    cfg = _read_json(path)
    if cfg is None:
        return

    servers: dict = cfg.get("mcpServers", {})
    if _SERVER_NAME not in servers:
        return

    if dry_run:
        print(f"  [dry-run] Would remove MCP server '{_SERVER_NAME}' from {path}")
        return

    servers.pop(_SERVER_NAME)
    _write_json(path, cfg)
    print(f"[claude] Removed MCP server '{_SERVER_NAME}' from settings.json")


# ── Codex ─────────────────────────────────────────────────────────────────────


def _install_codex(*, dry_run: bool) -> None:
    path = _CODEX_CONFIG
    content = _read_text(path)
    if content is None:
        return

    section_header = f"[mcp_servers.{_SERVER_NAME}]"
    if section_header in content:
        return  # already registered

    if dry_run:
        print(f"  [dry-run] Would add MCP server '{_SERVER_NAME}' to {path}")
        return

    path.write_text(content + _CODEX_TOML_BLOCK, encoding="utf-8")
    print(f"[codex] Registered MCP server '{_SERVER_NAME}' in config.toml")


def _uninstall_codex(*, dry_run: bool) -> None:
    path = _CODEX_CONFIG
    content = _read_text(path)
    if content is None:
        return

    section_header = f"[mcp_servers.{_SERVER_NAME}]"
    if section_header not in content:
        return

    # Remove the section: everything from the header to the next [section] or EOF
    import re
    # Match from [mcp_servers.pathly-telemetry] to next top-level section or EOF
    pattern = rf"\n?\[mcp_servers\.{re.escape(_SERVER_NAME)}\][^\[]*"
    cleaned = re.sub(pattern, "", content)

    if dry_run:
        print(f"  [dry-run] Would remove MCP server '{_SERVER_NAME}' from {path}")
        return

    path.write_text(cleaned, encoding="utf-8")
    print(f"[codex] Removed MCP server '{_SERVER_NAME}' from config.toml")


# ── helpers ───────────────────────────────────────────────────────────────────


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        print(f"  [warn] Config not found at {path}; skipping MCP setup.", file=sys.stderr)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  [warn] Could not read {path} ({exc}); skipping MCP setup.", file=sys.stderr)
        return None


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _read_text(path: Path) -> str | None:
    if not path.exists():
        print(f"  [warn] Config not found at {path}; skipping MCP setup.", file=sys.stderr)
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  [warn] Could not read {path} ({exc}); skipping MCP setup.", file=sys.stderr)
        return None
