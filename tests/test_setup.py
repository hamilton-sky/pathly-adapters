import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from install_cli.detect import detect_hosts, _HOST_MARKERS
from install_cli.materialize import materialize
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


def test_detect_claude_when_dir_missing(tmp_path, monkeypatch):
    with patch("install_cli.detect._HOST_MARKERS", {"claude": [tmp_path / "nonexistent"]}):
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


# ---------------------------------------------------------------------------
# setup_command
# ---------------------------------------------------------------------------

def test_no_flags_prints_no_writes_message(capsys):
    with patch.object(sys, "argv", ["pathly-setup"]):
        with patch("install_cli.setup_command.detect_hosts", return_value=["claude"]):
            main()
    captured = capsys.readouterr()
    assert "no writes" in captured.out.lower()
    assert "claude" in captured.out


def test_dry_run_calls_run_host_with_dry_run_true():
    with patch.object(sys, "argv", ["pathly-setup", "--dry-run"]):
        with patch("install_cli.setup_command.detect_hosts", return_value=["claude"]):
            with patch("install_cli.setup_command._run_host") as mock_run:
                main()
    mock_run.assert_called_once_with("claude", dry_run=True, repair=False, force=False)


def test_host_argument_limits_to_that_host():
    with patch.object(sys, "argv", ["pathly-setup", "claude", "--dry-run"]):
        with patch("install_cli.setup_command._run_host") as mock_run:
            main()
    mock_run.assert_called_once_with("claude", dry_run=True, repair=False, force=False)


def test_apply_calls_run_host_without_dry_run():
    with patch.object(sys, "argv", ["pathly-setup", "claude", "--apply"]):
        with patch("install_cli.setup_command._run_host") as mock_run:
            main()
    mock_run.assert_called_once_with("claude", dry_run=False, repair=False, force=False)


def test_no_detected_hosts_exits(capsys):
    with patch.object(sys, "argv", ["pathly-setup", "--dry-run"]):
        with patch("install_cli.setup_command.detect_hosts", return_value=[]):
            with pytest.raises(SystemExit) as exc:
                main()
    assert exc.value.code == 1


def test_dry_run_real_claude(capsys):
    """Integration smoke: pathly-setup claude --dry-run must not crash."""
    with patch.object(sys, "argv", ["pathly-setup", "claude", "--dry-run"]):
        main()  # no mocks — uses real adapter files
    captured = capsys.readouterr()
    assert "[claude]" in captured.out
