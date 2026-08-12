"""Default code-context backend resolution — `auto` (code-intel-auto-default).

`code_context.backend` now defaults to `auto`, which probes for an installed
backend (codebase-memory-mcp on PATH → cli; else uvx → lsp; else none), so
code-intelligence just-works wherever its external tools exist and cleanly no-ops
(→ Grep/Read) where they don't. An explicit off/cli/lsp/both still wins verbatim.
DB is isolated per-test by conftest._isolate_db (so the setting starts unset).
"""

from __future__ import annotations

from pathly_orchestrator.runner import code_context as cc


def _which_of(*present: str):
    """Fake shutil.which where only the named tools resolve (uses its arg)."""
    have = set(present)
    return lambda name: "/usr/bin/x" if name in have else None


def _setting(value: str):
    """Fake _get_setting returning `value` for code_context.backend (uses both args)."""

    def _get(key, default):
        return value if key == "code_context.backend" else default

    return _get


def test_default_auto_resolves_to_installed_backend(monkeypatch):
    # fresh isolated DB → no code_context.backend row → _resolve_backend uses "auto"
    monkeypatch.setattr(cc.shutil, "which", _which_of("codebase-memory-mcp"))
    assert cc._resolve_backend() == "cli"  # graph preferred for headless breadth

    monkeypatch.setattr(cc.shutil, "which", _which_of("uvx"))
    assert cc._resolve_backend() == "lsp"  # no graph binary, Serena via uvx

    monkeypatch.setattr(cc.shutil, "which", _which_of())
    assert cc._resolve_backend() == "none"  # neither → safe-off (Grep/Read)


def test_explicit_backend_overrides_auto(monkeypatch):
    # even with every tool present, an explicit setting wins and never auto-detects
    monkeypatch.setattr(cc.shutil, "which", _which_of("codebase-memory-mcp", "uvx"))
    for value, expected in [
        ("off", "none"),
        ("cli", "cli"),
        ("lsp", "lsp"),
        ("both", "both"),
        ("nonsense", "none"),
    ]:
        monkeypatch.setattr(cc, "_get_setting", _setting(value))
        assert cc._resolve_backend() == expected


def test_auto_backend_never_raises(monkeypatch):
    def _boom(name):
        raise RuntimeError(f"PATH probe failed for {name}")

    monkeypatch.setattr(cc.shutil, "which", _boom)
    assert cc._auto_backend() == "none"
