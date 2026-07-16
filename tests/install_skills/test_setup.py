import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from _paths import REPO_ROOT
from install_cli.detect import detect_hosts, _HOST_MARKERS
from install_cli.materialize import (
    materialize,
    materialize_flows,
    uninstall,
    MANIFEST_NAME,
)
from install_cli.setup_command import main

# ---------------------------------------------------------------------------
# detect
# ---------------------------------------------------------------------------


def test_detect_hosts_returns_list():
    result = detect_hosts()
    assert isinstance(result, list)
    assert all(isinstance(h, str) for h in result)


def test_host_markers_cover_all_supported_hosts():
    assert "claude" in _HOST_MARKERS
    assert "codex" in _HOST_MARKERS
    assert "copilot" in _HOST_MARKERS


def test_host_markers_cover_antigravity():
    assert "antigravity" in _HOST_MARKERS


def test_detect_antigravity_when_dir_exists(tmp_path):
    agy_dir = tmp_path / ".gemini" / "antigravity-cli"
    agy_dir.mkdir(parents=True)
    with patch("install_cli.detect._HOST_MARKERS", {"antigravity": [agy_dir]}):
        result = detect_hosts()
    assert "antigravity" in result


def test_detect_antigravity_when_dir_missing(tmp_path):
    with patch(
        "install_cli.detect._HOST_MARKERS", {"antigravity": [tmp_path / "nonexistent"]}
    ):
        result = detect_hosts()
    assert "antigravity" not in result


def test_detect_claude_when_dir_missing(tmp_path):
    with patch(
        "install_cli.detect._HOST_MARKERS", {"claude": [tmp_path / "nonexistent"]}
    ):
        result = detect_hosts()
    assert "claude" not in result


def test_detect_claude_when_dir_exists(tmp_path):
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    with patch("install_cli.detect._HOST_MARKERS", {"claude": [claude_dir]}):
        result = detect_hosts()
    assert "claude" in result


# ---------------------------------------------------------------------------
# materialize
# ---------------------------------------------------------------------------


def test_materialize_writes_new_files(tmp_path):
    files = {"agent.md": "# agent\n\nBody."}
    written = materialize(files, tmp_path)
    assert written == ["agent.md"]
    assert (tmp_path / "agent.md").read_text() == "# agent\n\nBody."


def test_materialize_dry_run_no_writes(tmp_path):
    files = {"agent.md": "# agent"}
    written = materialize(files, tmp_path / "dest", dry_run=True)
    assert written == ["agent.md"]
    assert not (tmp_path / "dest").exists()


def test_materialize_skips_non_owned_files(tmp_path):
    (tmp_path / "existing.md").write_text("user content")
    files = {"existing.md": "pathly content"}
    # No --force, not in manifest → skip
    written = materialize(files, tmp_path)
    assert written == []
    assert (tmp_path / "existing.md").read_text() == "user content"


def test_materialize_force_overwrites(tmp_path):
    (tmp_path / "existing.md").write_text("user content")
    files = {"existing.md": "pathly content"}
    written = materialize(files, tmp_path, force=True)
    assert written == ["existing.md"]
    assert (tmp_path / "existing.md").read_text() == "pathly content"


def test_materialize_repair_overwrites_owned(tmp_path):
    # First write creates ownership
    materialize({"agent.md": "v1"}, tmp_path)
    # Repair should update it
    written = materialize({"agent.md": "v2"}, tmp_path, repair=True)
    assert written == ["agent.md"]
    assert (tmp_path / "agent.md").read_text() == "v2"


def test_materialize_without_repair_skips_owned(tmp_path):
    materialize({"agent.md": "v1"}, tmp_path)
    written = materialize({"agent.md": "v2"}, tmp_path)  # no repair
    assert written == []
    assert (tmp_path / "agent.md").read_text() == "v1"


def test_materialize_repair_removes_obsolete_owned_files(tmp_path):
    materialize({"keep.md": "v1", "obsolete/SKILL.md": "old"}, tmp_path)

    written = materialize({"keep.md": "v2"}, tmp_path, repair=True)

    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert written == ["keep.md"]
    assert not (tmp_path / "obsolete" / "SKILL.md").exists()
    assert not (tmp_path / "obsolete").exists()
    assert "obsolete/SKILL.md" not in manifest["files"]


def test_materialize_flows_preserves_owned_agent_files(tmp_path):
    materialize({"orchestrator.md": "agent", "old.flow.yaml": "old"}, tmp_path)

    materialize_flows(tmp_path)

    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text(encoding="utf-8"))
    assert (tmp_path / "orchestrator.md").read_text(encoding="utf-8") == "agent"
    assert "orchestrator.md" in manifest["files"]
    assert not (tmp_path / "old.flow.yaml").exists()


# ---------------------------------------------------------------------------
# setup_command
# ---------------------------------------------------------------------------


def test_no_flags_launches_interactive_menu():
    # With no flags, main() delegates to _interactive_menu rather than writing
    # files directly. Patch the menu to return immediately (simulating Exit).
    with patch.object(sys, "argv", ["pathly-setup"]):
        with patch("install_cli.cli.detect_hosts", return_value=["claude"]):
            with patch("install_cli.cli._interactive_menu") as mock_menu:
                main()
    mock_menu.assert_called_once_with(["claude"], repair=False, force=False)


def test_dry_run_calls_run_host_with_dry_run_true():
    with patch.object(sys, "argv", ["pathly-setup", "--dry-run"]):
        with patch("install_cli.cli.detect_hosts", return_value=["claude"]):
            with patch("install_cli.cli._run_host") as mock_run:
                main()
    mock_run.assert_called_once_with("claude", dry_run=True, repair=False, force=False)


def test_host_argument_limits_to_that_host():
    with patch.object(sys, "argv", ["pathly-setup", "claude", "--dry-run"]):
        with patch("install_cli.cli._run_host") as mock_run:
            main()
    mock_run.assert_called_once_with("claude", dry_run=True, repair=False, force=False)


def test_apply_calls_run_host_without_dry_run():
    with patch.object(sys, "argv", ["pathly-setup", "claude", "--apply"]):
        with patch("install_cli.cli._run_host") as mock_run:
            main()
    mock_run.assert_called_once_with("claude", dry_run=False, repair=False, force=False)


def test_no_detected_hosts_exits():
    with patch.object(sys, "argv", ["pathly-setup", "--dry-run"]):
        with patch("install_cli.cli.detect_hosts", return_value=[]):
            with pytest.raises(SystemExit) as exc:
                main()
    assert exc.value.code == 1


def test_dry_run_real_claude(capsys):
    """Integration smoke: pathly-setup claude --dry-run must not crash."""
    with patch.object(sys, "argv", ["pathly-setup", "claude", "--dry-run"]):
        main()  # no mocks — uses real adapter files
    captured = capsys.readouterr()
    assert "[claude]" in captured.out


def test_dry_run_real_codex_includes_plugin_manifest(capsys):
    """Codex dry-run reports the plugin bundle manifest, not only skills/templates."""
    with patch.object(sys, "argv", ["pathly-setup", "codex", "--dry-run"]):
        main()  # no mocks — uses real adapter files
    captured = capsys.readouterr()
    assert "[codex]" in captured.out
    assert ".codex-plugin" in captured.out
    assert "plugin.json" in captured.out
    assert "skills" in captured.out
    assert "agents\\openai.yaml" in captured.out or "agents/openai.yaml" in captured.out
    assert "agents" in captured.out
    assert "templates" in captured.out
    assert "flows" in captured.out
    assert "team.flow.yaml" in captured.out


def test_codex_install_injects_execution_contract_into_skills(monkeypatch):
    from install_cli.orchestrate import _run_host

    captured_plugin_files = {}

    monkeypatch.setattr(
        "install_cli.orchestrate.materialize", lambda *args, **kwargs: []
    )
    monkeypatch.setattr(
        "install_cli.orchestrate.materialize_flows", lambda *args, **kwargs: []
    )

    def capture_plugin(files, **kwargs):
        captured_plugin_files.update(files)

    monkeypatch.setattr("install_cli.orchestrate.install_codex_plugin", capture_plugin)

    _run_host("codex", dry_run=False, repair=True, force=False)

    build_skill = captured_plugin_files["skills/pathly-build/SKILL.md"]
    assert "## Codex Execution Contract" in build_skill
    assert "agent_hint" in build_skill
    assert "`worker`" in build_skill
    assert "`explorer`" in build_skill
    assert (
        "Never block or claim failure solely because a named Pathly role" in build_skill
    )
    assert build_skill.index("## Codex Execution Contract") < build_skill.index(
        "# build"
    )

    builder_agent = captured_plugin_files["agents/builder.toml"]
    assert "pathly-fsm-call record-activity" in builder_agent


# ---------------------------------------------------------------------------
# SKILL_EXECUTION.md — adapter integration contract assertions
# ---------------------------------------------------------------------------


def test_skill_execution_md_decision_values():
    """SKILL_EXECUTION.md must document all three FSM decision values."""
    skill_exec = (
        REPO_ROOT / "src" / "pathly_data" / "adapters" / "codex" / "SKILL_EXECUTION.md"
    )
    content = skill_exec.read_text(encoding="utf-8")
    assert "continue" in content
    assert "block" in content
    assert "escalate" in content


def test_skill_execution_md_agent_hint_is_primary():
    """SKILL_EXECUTION.md must reference agent_hint as primary contract."""
    skill_exec = (
        REPO_ROOT / "src" / "pathly_data" / "adapters" / "codex" / "SKILL_EXECUTION.md"
    )
    content = skill_exec.read_text(encoding="utf-8")
    assert "agent_hint" in content


def test_skill_execution_md_no_codex_subagent_primary_dispatch():
    """codex_subagent must not appear as a primary dispatch reference."""
    skill_exec = (
        REPO_ROOT / "src" / "pathly_data" / "adapters" / "codex" / "SKILL_EXECUTION.md"
    )
    content = skill_exec.read_text(encoding="utf-8")
    assert "codex_subagent" not in content


# ---------------------------------------------------------------------------
# uninstall — manifest traversal guard
# ---------------------------------------------------------------------------


def _write_manifest(dest: Path, entries: dict) -> None:
    manifest_hash = hashlib.sha256(
        json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    manifest = {
        "_manifest_version": "1",
        "_manifest_hash": manifest_hash,
        "files": entries,
    }
    (dest / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def test_uninstall_rejects_traversal_in_manifest(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    _write_manifest(dest, {"../../evil_file": "2024-01-01T00:00:00+00:00"})

    evil_file = tmp_path / "evil_file"
    evil_file.write_text("untouched", encoding="utf-8")

    with pytest.raises(ValueError, match="traversal"):
        uninstall(dest)

    assert evil_file.exists(), "File outside dest must not be deleted"


def test_uninstall_clean_manifest(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    tracked_file = dest / "agent.md"
    tracked_file.write_text("# agent", encoding="utf-8")
    _write_manifest(dest, {"agent.md": "2024-01-01T00:00:00+00:00"})

    removed = uninstall(dest)

    assert removed == ["agent.md"]
    assert not tracked_file.exists()


def test_materialize_raises_on_tampered_manifest(tmp_path):
    from install_cli.materialize import materialize, MANIFEST_NAME

    # Write a manifest with a bad hash
    manifest = {
        "_manifest_version": "1",
        "_manifest_hash": "deadbeef",  # wrong hash
        "files": {"agent.md": "2024-01-01T00:00:00+00:00"},
    }
    (tmp_path / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    (tmp_path / "agent.md").write_text("# agent", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Manifest integrity check failed"):
        materialize({"agent.md": "# updated"}, tmp_path)


# ---------------------------------------------------------------------------
# _apply_hooks — stop-hook path-corruption fix
# ---------------------------------------------------------------------------


def _stop_commands(settings: dict) -> list[str]:
    """Extract all stop-hook command strings from a settings dict."""
    return [
        h.get("command", "")
        for g in settings.get("hooks", {}).get("Stop", [])
        for h in (g.get("hooks", []) if isinstance(g, dict) else [])
        if isinstance(h, dict)
    ]


def test_apply_hooks_writes_settings_json(tmp_path):
    """First install creates settings.json with the python -m stop hook."""
    from install_cli.orchestrate import _apply_hooks

    settings_path = tmp_path / ".claude" / "settings.json"
    hooks_cfg = {
        "settings_dest": str(settings_path),
        "Stop": ["python -m pathly_hooks.stop_telemetry"],
    }
    _apply_hooks("claude", hooks_cfg, dry_run=False, repair=False)

    settings = json.loads(settings_path.read_text())
    assert "python -m pathly_hooks.stop_telemetry" in _stop_commands(settings)


def test_apply_hooks_repair_replaces_stale_path(tmp_path):
    """repair=True replaces the old hardcoded-path command with python -m form."""
    from install_cli.orchestrate import _apply_hooks

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    old_cmd = (
        "python C:\\Users\\Yafit\\pathly-adapters\\src\\pathly_hooks\\stop_telemetry.py"
    )
    old_settings = {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": old_cmd}]}]}
    }
    settings_path.write_text(json.dumps(old_settings))

    hooks_cfg = {
        "settings_dest": str(settings_path),
        "Stop": ["python -m pathly_hooks.stop_telemetry"],
    }
    _apply_hooks("claude", hooks_cfg, dry_run=False, repair=True)

    cmds = _stop_commands(json.loads(settings_path.read_text()))
    assert "python -m pathly_hooks.stop_telemetry" in cmds
    assert old_cmd not in cmds


def test_apply_hooks_no_repair_preserves_existing_pathly_hook(tmp_path):
    """Without repair, an existing Pathly hook is not overwritten."""
    from install_cli.orchestrate import _apply_hooks

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    old_cmd = (
        "python C:\\Users\\Yafit\\pathly-adapters\\src\\pathly_hooks\\stop_telemetry.py"
    )
    old_settings = {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": old_cmd}]}]}
    }
    settings_path.write_text(json.dumps(old_settings))

    hooks_cfg = {
        "settings_dest": str(settings_path),
        "Stop": ["python -m pathly_hooks.stop_telemetry"],
    }
    _apply_hooks("claude", hooks_cfg, dry_run=False, repair=False)

    cmds = _stop_commands(json.loads(settings_path.read_text()))
    assert old_cmd in cmds


def test_apply_hooks_preserves_non_pathly_hooks(tmp_path):
    """Installing Pathly hooks never removes third-party hooks."""
    from install_cli.orchestrate import _apply_hooks

    settings_path = tmp_path / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True)
    other_cmd = "some-other-tool --cleanup"
    old_settings = {
        "hooks": {"Stop": [{"hooks": [{"type": "command", "command": other_cmd}]}]}
    }
    settings_path.write_text(json.dumps(old_settings))

    hooks_cfg = {
        "settings_dest": str(settings_path),
        "Stop": ["python -m pathly_hooks.stop_telemetry"],
    }
    _apply_hooks("claude", hooks_cfg, dry_run=False, repair=False)

    cmds = _stop_commands(json.loads(settings_path.read_text()))
    assert other_cmd in cmds
    assert "python -m pathly_hooks.stop_telemetry" in cmds


def test_apply_hooks_dry_run_does_not_write(tmp_path, capsys):
    """dry_run=True prints a message but does not create the file."""
    from install_cli.orchestrate import _apply_hooks

    settings_path = tmp_path / ".claude" / "settings.json"
    hooks_cfg = {
        "settings_dest": str(settings_path),
        "Stop": ["python -m pathly_hooks.stop_telemetry"],
    }
    _apply_hooks("claude", hooks_cfg, dry_run=True, repair=False)

    assert not settings_path.exists()
    captured = capsys.readouterr()
    assert "Would update hooks" in captured.out


def test_apply_hooks_install_yaml_uses_module_notation():
    """install.yaml stop hook must use 'python -m' to avoid shell backslash issues."""
    import yaml as _yaml

    install_yaml = (
        REPO_ROOT
        / "src"
        / "pathly_data"
        / "adapters"
        / "claude"
        / "_meta"
        / "install.yaml"
    )
    cfg = _yaml.safe_load(install_yaml.read_text(encoding="utf-8"))
    stop_cmds = cfg.get("hooks", {}).get("Stop", [])
    assert stop_cmds, "install.yaml must declare at least one Stop hook"
    assert all(
        cmd.startswith("python -m") for cmd in stop_cmds
    ), "Stop hook commands must use 'python -m' notation (no hardcoded paths)"
