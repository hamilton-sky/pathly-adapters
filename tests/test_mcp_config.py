"""Tests for src/install_cli/mcp_config.py.

Monkeypatches _CLAUDE_SETTINGS and _CODEX_CONFIG to temp files so no
real host config files are touched.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import install_cli.mcp_config as mcp_config
from install_cli.mcp_config import install_mcp_config, uninstall_mcp_config

_SERVER_NAME = "pathly-telemetry"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _patch_claude(monkeypatch, settings_path: Path) -> None:
    monkeypatch.setattr(mcp_config, "_CLAUDE_SETTINGS", settings_path)


def _patch_codex(monkeypatch, config_path: Path) -> None:
    monkeypatch.setattr(mcp_config, "_CODEX_CONFIG", config_path)


def _write_json(path: Path, obj: dict) -> None:
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ===========================================================================
# Claude tests
# ===========================================================================

def test_install_adds_entry_claude(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    _write_json(settings, {})
    _patch_claude(monkeypatch, settings)

    install_mcp_config("claude")

    cfg = _read_json(settings)
    assert _SERVER_NAME in cfg["mcpServers"]


def test_uninstall_removes_entry_claude(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    _write_json(settings, {"mcpServers": {_SERVER_NAME: {"command": "python", "args": ["-m", "pathly_telemetry"]}}})
    _patch_claude(monkeypatch, settings)

    uninstall_mcp_config("claude")

    cfg = _read_json(settings)
    assert _SERVER_NAME not in cfg.get("mcpServers", {})


def test_dry_run_no_changes_claude(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    original = {}
    _write_json(settings, original)
    _patch_claude(monkeypatch, settings)

    install_mcp_config("claude", dry_run=True)

    cfg = _read_json(settings)
    assert _SERVER_NAME not in cfg.get("mcpServers", {})


def test_missing_config_file_claude(monkeypatch, tmp_path):
    settings = tmp_path / "nonexistent_settings.json"
    _patch_claude(monkeypatch, settings)

    install_mcp_config("claude")
    uninstall_mcp_config("claude")


def test_install_invalid_json_claude(monkeypatch, tmp_path, capsys):
    settings = tmp_path / "settings.json"
    settings.write_text("not valid json {{", encoding="utf-8")
    _patch_claude(monkeypatch, settings)

    install_mcp_config("claude")

    captured = capsys.readouterr()
    assert "warn" in captured.err.lower() or "warn" in captured.out.lower()


def test_install_idempotent_claude(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    _write_json(settings, {})
    _patch_claude(monkeypatch, settings)

    install_mcp_config("claude")
    install_mcp_config("claude")

    cfg = _read_json(settings)
    servers = cfg.get("mcpServers", {})
    assert list(servers.keys()).count(_SERVER_NAME) == 1


def test_install_idempotent_different_args_claude(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    _write_json(settings, {})
    _patch_claude(monkeypatch, settings)

    install_mcp_config("claude")

    cfg = _read_json(settings)
    cfg["mcpServers"][_SERVER_NAME]["args"] = ["-m", "pathly_telemetry", "--custom"]
    _write_json(settings, cfg)

    install_mcp_config("claude")

    cfg_after = _read_json(settings)
    assert cfg_after["mcpServers"][_SERVER_NAME]["args"] == ["-m", "pathly_telemetry", "--custom"]


def test_uninstall_missing_entry_claude(monkeypatch, tmp_path):
    settings = tmp_path / "settings.json"
    _write_json(settings, {"mcpServers": {}})
    _patch_claude(monkeypatch, settings)

    uninstall_mcp_config("claude")

    cfg = _read_json(settings)
    assert _SERVER_NAME not in cfg.get("mcpServers", {})


# ===========================================================================
# Codex tests
# ===========================================================================

def test_install_adds_entry_codex(monkeypatch, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    _patch_codex(monkeypatch, config)

    install_mcp_config("codex")

    content = config.read_text(encoding="utf-8")
    assert f"[mcp_servers.{_SERVER_NAME}]" in content


def test_install_codex_adds_pythonpath_for_mcp_imports(monkeypatch, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    _patch_codex(monkeypatch, config)

    install_mcp_config("codex")

    content = config.read_text(encoding="utf-8")
    assert 'PYTHONPATH = "' in content
    assert "pathly-telemetry.env" in content
    assert "pathly-fsm.env" in content


def test_uninstall_removes_entry_codex(monkeypatch, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text(
        f"\n[mcp_servers.{_SERVER_NAME}]\ncommand = \"python\"\nargs = [\"-m\", \"pathly_telemetry\"]\n",
        encoding="utf-8",
    )
    _patch_codex(monkeypatch, config)

    uninstall_mcp_config("codex")

    content = config.read_text(encoding="utf-8")
    assert f"[mcp_servers.{_SERVER_NAME}]" not in content


def test_dry_run_no_changes_codex(monkeypatch, tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("", encoding="utf-8")
    _patch_codex(monkeypatch, config)

    install_mcp_config("codex", dry_run=True)

    content = config.read_text(encoding="utf-8")
    assert f"[mcp_servers.{_SERVER_NAME}]" not in content


def test_missing_config_file_codex(monkeypatch, tmp_path):
    config = tmp_path / "nonexistent_config.toml"
    _patch_codex(monkeypatch, config)

    install_mcp_config("codex")
    uninstall_mcp_config("codex")


def test_uninstall_removes_full_block_including_args_codex(monkeypatch, tmp_path):
    """Uninstall must remove the args line whose value contains '[', not stop at it."""
    config = tmp_path / "config.toml"
    config.write_text("[memories]\nsome = true\n", encoding="utf-8")
    _patch_codex(monkeypatch, config)

    install_mcp_config("codex")
    uninstall_mcp_config("codex")

    content = config.read_text(encoding="utf-8")
    assert f"[mcp_servers.{_SERVER_NAME}]" not in content
    assert "pathly_telemetry" not in content


def test_repeated_install_uninstall_no_accumulation_codex(monkeypatch, tmp_path):
    """Three install+uninstall cycles must leave no trace."""
    config = tmp_path / "config.toml"
    config.write_text("[memories]\nsome = true\n", encoding="utf-8")
    _patch_codex(monkeypatch, config)

    for _ in range(3):
        install_mcp_config("codex")
        uninstall_mcp_config("codex")

    content = config.read_text(encoding="utf-8")
    assert "pathly_telemetry" not in content


def test_uninstall_cleans_stale_bare_args_line_codex(monkeypatch, tmp_path):
    """Uninstall strips bare '["-m", "pathly_telemetry"]' lines from prior buggy runs."""
    config = tmp_path / "config.toml"
    config.write_text(
        '[memories]\nsome = true\n["-m", "pathly_telemetry"]\n',
        encoding="utf-8",
    )
    _patch_codex(monkeypatch, config)

    uninstall_mcp_config("codex")

    content = config.read_text(encoding="utf-8")
    assert '["-m", "pathly_telemetry"]' not in content
    assert "[memories]" in content
