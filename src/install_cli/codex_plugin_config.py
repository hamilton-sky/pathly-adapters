"""Install/remove Pathly's Codex local marketplace registration."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

MARKETPLACE_NAME = "pathly-local"
PLUGIN_NAME = "pathly"

_CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
_MARKETPLACE_ROOT = Path.home() / ".codex" / "pathly-marketplace"
_PLUGIN_CACHE_ROOT = Path.home() / ".codex" / "plugins" / "cache" / MARKETPLACE_NAME / PLUGIN_NAME


def _write_error(action: str, path: Path, exc: OSError) -> RuntimeError:
    return RuntimeError(f"Cannot {action} {path}: {exc}. Check that the Codex config directory is writable.")


def install_codex_plugin(
    plugin_files: dict[str, str],
    *,
    dry_run: bool = False,
    config_path: Path | None = None,
    marketplace_root: Path | None = None,
    codex_command: str | None = None,
) -> None:
    """Create a real local marketplace and enable the Pathly plugin."""
    config_path = config_path or _CODEX_CONFIG
    marketplace_root = marketplace_root or _MARKETPLACE_ROOT

    if dry_run:
        print(f"  [dry-run] Would write Codex marketplace to {marketplace_root}")
        print(f"  [dry-run] Would enable plugin '{PLUGIN_NAME}@{MARKETPLACE_NAME}' in {config_path}")
        print("  [dry-run] Would refresh Codex local marketplace registration if the codex CLI is available")
        return

    using_default_paths = config_path == _CODEX_CONFIG and marketplace_root == _MARKETPLACE_ROOT
    plugin_root = marketplace_root / "plugins" / PLUGIN_NAME
    if plugin_root.exists():
        shutil.rmtree(plugin_root)
    try:
        plugin_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _write_error("create Codex plugin directory", plugin_root, exc) from exc

    for name, content in sorted(plugin_files.items()):
        target = plugin_root / name
        if not target.resolve().is_relative_to(plugin_root.resolve()):
            raise ValueError(f"Path traversal detected in plugin file: {name!r}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise _write_error("write Codex plugin file", target, exc) from exc

    _write_marketplace_json(marketplace_root)
    _write_plugin_cache(plugin_files)
    refreshed = _refresh_codex_marketplace(
        marketplace_root,
        codex_command=codex_command,
        discover_cli=using_default_paths,
    )
    if not refreshed:
        _enable_in_codex_config(config_path, marketplace_root)
    print(f"[codex] Registered local plugin marketplace at {marketplace_root}")
    print('[codex] Restart Codex and start a new thread. Try: "Use Pathly help"')


def uninstall_codex_plugin(
    *,
    dry_run: bool = False,
    config_path: Path | None = None,
    marketplace_root: Path | None = None,
) -> None:
    config_path = config_path or _CODEX_CONFIG
    marketplace_root = marketplace_root or _MARKETPLACE_ROOT

    if dry_run:
        print(f"  [dry-run] Would remove plugin '{PLUGIN_NAME}@{MARKETPLACE_NAME}' from {config_path}")
        print(f"  [dry-run] Would remove Codex marketplace at {marketplace_root}")
        return

    _disable_in_codex_config(config_path)
    if marketplace_root.exists():
        shutil.rmtree(marketplace_root)
    if _PLUGIN_CACHE_ROOT.exists():
        shutil.rmtree(_PLUGIN_CACHE_ROOT)
    print(f"[codex] Removed local plugin marketplace at {marketplace_root}")


def _write_marketplace_json(root: Path) -> None:
    path = root / ".agents" / "plugins" / "marketplace.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise _write_error("create Codex marketplace metadata directory", path.parent, exc) from exc
    data = {
        "name": MARKETPLACE_NAME,
        "interface": {"displayName": "Pathly Local"},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Developer Tools",
            }
        ],
    }
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError as exc:
        raise _write_error("write Codex marketplace metadata", path, exc) from exc


def _plugin_version(plugin_files: dict[str, str]) -> str:
    return "local"


def _write_plugin_cache(plugin_files: dict[str, str]) -> None:
    cache_root = _PLUGIN_CACHE_ROOT / _plugin_version(plugin_files)
    if cache_root.exists():
        try:
            shutil.rmtree(cache_root)
        except OSError as exc:
            raise _write_error("replace Codex plugin cache", cache_root, exc) from exc

    for name, content in sorted(plugin_files.items()):
        target = cache_root / name
        if not target.resolve().is_relative_to(cache_root.resolve()):
            raise ValueError(f"Path traversal detected in plugin cache file: {name!r}")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise _write_error("write Codex plugin cache file", target, exc) from exc


def _refresh_codex_marketplace(
    marketplace_root: Path,
    *,
    codex_command: str | None = None,
    discover_cli: bool = True,
) -> bool:
    command = codex_command
    if command is None and discover_cli:
        command = shutil.which("codex")
    if command is None:
        print("[codex] Codex CLI not found; config.toml was updated directly.")
        return False

    try:
        remove = subprocess.run(
            [command, "plugin", "marketplace", "remove", MARKETPLACE_NAME],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as exc:
        print(f"[codex] Codex CLI could not be launched: {exc}", file=sys.stderr)
        print("[codex] Falling back to direct config.toml registration.", file=sys.stderr)
        return False
    if remove.returncode != 0:
        print(f"[codex] Marketplace remove skipped: {remove.stderr.strip() or remove.stdout.strip()}")

    try:
        add = subprocess.run(
            [command, "plugin", "marketplace", "add", str(marketplace_root)],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except OSError as exc:
        print(f"[codex] Codex CLI could not be launched: {exc}", file=sys.stderr)
        print("[codex] Falling back to direct config.toml registration.", file=sys.stderr)
        return False
    if add.returncode != 0:
        print(f"[codex] Codex CLI marketplace refresh failed: {add.stderr.strip() or add.stdout.strip()}", file=sys.stderr)
        print("[codex] Falling back to direct config.toml registration.", file=sys.stderr)
        return False

    print("[codex] Refreshed Codex local marketplace registration via codex CLI.")
    return True


def _enable_in_codex_config(path: Path, marketplace_root: Path) -> None:
    content = _read_config(path)
    content = _remove_pathly_blocks(content)
    block = (
        f"\n[marketplaces.{MARKETPLACE_NAME}]\n"
        'last_updated = "1970-01-01T00:00:00Z"\n'
        'source_type = "local"\n'
        f"source = '{marketplace_root}'\n"
        f'[plugins."{PLUGIN_NAME}@{MARKETPLACE_NAME}"]\n'
        "enabled = true\n"
    )
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content.rstrip() + "\n" + block, encoding="utf-8")
    except OSError as exc:
        raise _write_error("write Codex config", path, exc) from exc


def _disable_in_codex_config(path: Path) -> None:
    content = _read_config(path)
    cleaned = _remove_pathly_blocks(content)
    if cleaned != content:
        path.write_text(cleaned.rstrip() + "\n", encoding="utf-8")


def _read_config(path: Path) -> str:
    if not path.exists():
        print(f"  [warn] Codex config not found at {path}; creating it.", file=sys.stderr)
        return ""
    return path.read_text(encoding="utf-8")


def _remove_pathly_blocks(content: str) -> str:
    marketplace = rf"\n?\[marketplaces\.{re.escape(MARKETPLACE_NAME)}\].*?(?=\n\[|\Z)"
    plugin = rf"\n?\[plugins\.\"{re.escape(PLUGIN_NAME)}@{re.escape(MARKETPLACE_NAME)}\"\].*?(?=\n\[|\Z)"
    content = re.sub(marketplace, "", content, flags=re.DOTALL)
    content = re.sub(plugin, "", content, flags=re.DOTALL)
    return content
