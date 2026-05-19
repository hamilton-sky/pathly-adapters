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


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _package_import_root() -> str:
    """Return the directory that makes Pathly packages importable."""
    return str(Path(__file__).resolve().parents[1])


# The MCP server is run via  python -m pathly_telemetry
_CLAUDE_ENTRY: dict = {
    "command": "python",
    "args": ["-m", "pathly_telemetry"],
}

_CODEX_TOML_BLOCK = (
    f"\n[mcp_servers.{_SERVER_NAME}]\n"
    f'command = "{_toml_escape(sys.executable)}"\n'
    'args = ["-u", "-m", "pathly_telemetry"]\n'
    "startup_timeout_sec = 60\n"
    f"\n[mcp_servers.{_SERVER_NAME}.env]\n"
    'PYTHONUNBUFFERED = "1"\n'
    'PYTHONIOENCODING = "utf-8"\n'
    f'PYTHONPATH = "{_toml_escape(_package_import_root())}"\n'
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
    if servers.get(_SERVER_NAME) == _CLAUDE_ENTRY:
        return  # already up to date

    if dry_run:
        print(f"  [dry-run] Would add/update MCP server '{_SERVER_NAME}' in {path}")
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
    import re as _re

    path = _CODEX_CONFIG
    content = _read_text(path)
    if content is None:
        return

    section_header = f"[mcp_servers.{_SERVER_NAME}]"
    expected_command = sys.executable.replace("\\", "\\\\")
    if section_header in content and expected_command in content:
        return  # already up to date

    if dry_run:
        print(f"  [dry-run] Would add/update MCP server '{_SERVER_NAME}' in {path}")
        return

    if section_header in content:
        pattern = rf"\n?\[mcp_servers\.{_re.escape(_SERVER_NAME)}\].*?(?=\n\[|\Z)"
        content = _re.sub(pattern, "", content, flags=_re.DOTALL)

    path.write_text(content + _CODEX_TOML_BLOCK, encoding="utf-8")
    print(f"[codex] Registered MCP server '{_SERVER_NAME}' in config.toml")


def _uninstall_codex(*, dry_run: bool) -> None:
    path = _CODEX_CONFIG
    content = _read_text(path)
    if content is None:
        return

    import re

    cleaned = content

    section_header = f"[mcp_servers.{_SERVER_NAME}]"
    if section_header in cleaned:
        # Remove from the section header to the next top-level section (a '['
        # at line start) or EOF.  re.DOTALL lets '.' cross newlines in the block.
        pattern = rf"\n?\[mcp_servers\.{re.escape(_SERVER_NAME)}\].*?(?=\n\[|\Z)"
        cleaned = re.sub(pattern, "", cleaned, flags=re.DOTALL)

    # Strip any stale bare args lines left by previous buggy uninstalls.
    _STALE_ARGS_LINE = '["-m", "pathly_telemetry"]'
    cleaned = "\n".join(
        line for line in cleaned.split("\n")
        if line.strip() != _STALE_ARGS_LINE
    )

    if cleaned == content:
        return

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
