"""Tests for multi-adapter runner Conv 1 — adapters.yaml, resolve_command, TS staleness."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parent.parent


# ── Phase 1: adapters.yaml shape ──────────────────────────────────────────────


def test_adapters_yaml_loads():
    from importlib.resources import files

    text = (
        files("pathly_data").joinpath("core/adapters.yaml").read_text(encoding="utf-8")
    )
    data = yaml.safe_load(text)
    assert set(data.keys()) == {"claude", "codex", "copilot", "antigravity"}


def test_adapters_yaml_required_keys():
    from importlib.resources import files

    data = yaml.safe_load(
        files("pathly_data").joinpath("core/adapters.yaml").read_text(encoding="utf-8")
    )
    required = {"terminal_kind", "headless", "autonomy_flag", "resume", "parse"}
    for name, cfg in data.items():
        missing = required - set(cfg.keys())
        assert not missing, f"{name} missing keys: {missing}"


def test_copilot_has_null_headless_and_resume():
    from importlib.resources import files

    data = yaml.safe_load(
        files("pathly_data").joinpath("core/adapters.yaml").read_text(encoding="utf-8")
    )
    assert data["copilot"]["headless"] is None
    assert data["copilot"]["resume"] is None


# ── Phase 2: resolve_command ──────────────────────────────────────────────────

from pathly_orchestrator.adapters import resolve_command


def test_resolve_command_claude_defaults():
    result = resolve_command("claude", "do stuff", "claude-sonnet-4-6")
    assert result["terminal_kind"] == "claude"
    assert result["supports_resume"] is True
    argv = result["argv"]
    assert argv[0] == "claude"
    assert "-p" in argv
    assert "do stuff" in argv
    assert "--model" in argv
    assert "claude-sonnet-4-6" in argv
    assert "--output-format" in argv
    assert "json" in argv
    assert "--dangerously-skip-permissions" in argv


def test_resolve_command_claude_no_autonomy():
    result = resolve_command("claude", "do stuff", "claude-sonnet-4-6", autonomy=False)
    assert "--dangerously-skip-permissions" not in result["argv"]


def test_resolve_command_claude_with_session():
    result = resolve_command(
        "claude", "do stuff", "claude-sonnet-4-6", session="sess123"
    )
    argv = result["argv"]
    assert "--resume" in argv
    idx = argv.index("--resume")
    assert argv[idx + 1] == "sess123"


def test_resolve_command_codex():
    result = resolve_command("codex", "do stuff", "gpt-4o")
    assert result["terminal_kind"] == "codex"
    assert result["supports_resume"] is True
    argv = result["argv"]
    assert argv[0] == "codex"
    assert "exec" in argv
    assert "--sandbox" in argv
    assert "workspace-write" in argv


def test_resolve_command_copilot_raises():
    with pytest.raises(ValueError, match="no headless mode"):
        resolve_command("copilot", "do stuff", "gpt-4o")


def test_resolve_command_unknown_adapter_raises():
    with pytest.raises(ValueError, match="Unknown adapter"):
        resolve_command("turbo-ai", "do stuff", "model-x")


# ── Phase 2b: headless-capability helpers (run-start adapter validation) ──────

from pathly_orchestrator.adapters import (  # noqa: E402
    headless_capable,
    unsupported_headless_adapters,
)


def test_headless_capable_true_for_claude_codex():
    assert headless_capable("claude") is True
    assert headless_capable("codex") is True


def test_headless_capable_false_for_null_and_unknown():
    assert headless_capable("copilot") is False  # headless: null
    assert headless_capable("turbo-ai") is False  # unknown adapter
    assert headless_capable("antigravity") is True  # agy -p one-shot template wired


def test_unsupported_headless_adapters_filters_sorts_and_dedups():
    bad = unsupported_headless_adapters(
        ["claude", "codex", "copilot", "antigravity", "copilot", "claude"]
    )
    assert bad == ["copilot"]  # antigravity now has a headless template; only copilot lacks one


def test_unsupported_headless_adapters_empty_when_all_supported():
    assert unsupported_headless_adapters(["claude", "codex", "claude"]) == []


def test_unsupported_headless_adapters_ignores_blanks():
    assert unsupported_headless_adapters(["", "claude", ""]) == []


# ── Phase 3: adapters.gen.ts staleness ───────────────────────────────────────


def test_adapters_gen_ts_is_not_stale():
    """Fails if the committed adapters.gen.ts diverges from what the generator would produce."""
    gen_script = ROOT / "scripts" / "gen_adapters_ts.py"
    out_ts = ROOT / "studio" / "src" / "renderer" / "src" / "lib" / "adapters.gen.ts"

    assert gen_script.exists(), f"Generator script not found: {gen_script}"
    assert (
        out_ts.exists()
    ), f"adapters.gen.ts not found: {out_ts}. Run: python scripts/gen_adapters_ts.py"

    # Import the generator's generate() function directly without writing to disk
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import importlib

        gen_mod = importlib.import_module("gen_adapters_ts")
        importlib.reload(gen_mod)
    finally:
        sys.path.pop(0)

    adapters_yaml = ROOT / "src" / "pathly_data" / "core" / "adapters.yaml"
    adapters = yaml.safe_load(adapters_yaml.read_text(encoding="utf-8"))
    expected = gen_mod.generate(adapters)

    committed = out_ts.read_text(encoding="utf-8")
    assert (
        committed == expected
    ), "adapters.gen.ts is stale. Run `python scripts/gen_adapters_ts.py` to regenerate."
