"""Tests for deploy/remove codex and copilot hook functions in materialize.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from install_cli.materialize import (
    deploy_codex_hooks,
    deploy_copilot_hooks,
    remove_codex_hooks,
    remove_copilot_hooks,
)


def test_deploy_codex_hooks_writes_pathly_key():
    paths = deploy_codex_hooks(dry_run=True)
    assert len(paths) == 1
    assert "hooks.json" in paths[0]


def test_deploy_codex_hooks_merges_existing(tmp_path, monkeypatch):
    fake_codex_dir = tmp_path / ".codex"
    fake_codex_dir.mkdir()
    hooks_file = fake_codex_dir / "hooks.json"
    hooks_file.write_text(json.dumps({"user": {"my_hook": {"event": "PostToolUse"}}}), encoding="utf-8")

    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    deploy_codex_hooks(dry_run=False)

    result = json.loads(hooks_file.read_text(encoding="utf-8"))
    assert "user" in result, "user key must be preserved"
    assert result["user"] == {"my_hook": {"event": "PostToolUse"}}
    assert "pathly" in result, "pathly key must be added"
    assert "classify_feedback" in result["pathly"]
    assert "inject_feedback_ttl" in result["pathly"]


def test_remove_codex_hooks_removes_pathly_key(tmp_path, monkeypatch):
    fake_codex_dir = tmp_path / ".codex"
    fake_codex_dir.mkdir()

    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    deploy_codex_hooks(dry_run=False)

    hooks_file = fake_codex_dir / "hooks.json"
    before = json.loads(hooks_file.read_text(encoding="utf-8"))
    assert "pathly" in before

    # Add a user key so the file is not empty after removal
    before["user"] = {"my_hook": {"event": "PostToolUse"}}
    hooks_file.write_text(json.dumps(before), encoding="utf-8")

    remove_codex_hooks(dry_run=False)

    after = json.loads(hooks_file.read_text(encoding="utf-8"))
    assert "pathly" not in after
    assert "user" in after


def test_deploy_copilot_hooks_writes_two_files(tmp_path):
    dest = tmp_path / ".github" / "hooks"
    deploy_copilot_hooks(dest=dest, dry_run=False)

    classify_file = dest / "pathly-classify.json"
    ttl_file = dest / "pathly-ttl.json"
    assert classify_file.exists(), "pathly-classify.json must be created"
    assert ttl_file.exists(), "pathly-ttl.json must be created"

    classify_data = json.loads(classify_file.read_text(encoding="utf-8"))
    assert classify_data["event"] == "PostToolUse"
    assert "command" in classify_data
    assert "windows" in classify_data["command"]
    assert "linux" in classify_data["command"]
    assert "osx" in classify_data["command"]

    ttl_data = json.loads(ttl_file.read_text(encoding="utf-8"))
    assert ttl_data["event"] == "PostToolUse"
    assert "command" in ttl_data


def test_remove_copilot_hooks_deletes_files(tmp_path):
    dest = tmp_path / ".github" / "hooks"
    deploy_copilot_hooks(dest=dest, dry_run=False)

    classify_file = dest / "pathly-classify.json"
    ttl_file = dest / "pathly-ttl.json"
    assert classify_file.exists()
    assert ttl_file.exists()

    remove_copilot_hooks(dest=dest, dry_run=False)

    assert not classify_file.exists(), "pathly-classify.json must be deleted"
    assert not ttl_file.exists(), "pathly-ttl.json must be deleted"


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))

    copilot_dest = tmp_path / ".github" / "hooks"

    codex_paths = deploy_codex_hooks(dry_run=True)
    copilot_paths = deploy_copilot_hooks(dest=copilot_dest, dry_run=True)

    assert len(codex_paths) > 0, "dry-run must return non-empty path list for codex"
    assert len(copilot_paths) > 0, "dry-run must return non-empty path list for copilot"

    # No files should have been written
    codex_hooks = fake_home / ".codex" / "hooks.json"
    assert not codex_hooks.exists(), "hooks.json must not be written during dry-run"
    assert not copilot_dest.exists(), ".github/hooks must not be created during dry-run"
