from pathlib import Path
from unittest.mock import patch

import pytest

from install_cli.materialize import materialize, uninstall, MANIFEST_NAME

# ---------------------------------------------------------------------------
# Rollback on mid-install failure
#
# materialize() has no write-rollback logic, so files written before a failure
# are left on disk.  The rollback flow is: catch the OSError from materialize(),
# then call uninstall(dest) to clean up.  This test verifies that the
# rollback-via-uninstall flow leaves no manifest on disk.
# ---------------------------------------------------------------------------


def test_no_orphans_after_mid_install_failure(tmp_path):
    """Mid-install OSError followed by uninstall() leaves no manifest on disk."""
    files = {
        "file_a.md": "# file A",
        "file_b.md": "# file B",
        "file_c.md": "# file C",
    }

    call_count = {"n": 0}
    original_write_text = Path.write_text

    def patched_write_text(self, data, encoding=None, errors=None):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("Simulated disk failure on write #2")
        if encoding is not None and errors is not None:
            return original_write_text(self, data, encoding, errors)
        if encoding is not None:
            return original_write_text(self, data, encoding)
        return original_write_text(self, data)

    with patch.object(Path, "write_text", patched_write_text):
        try:
            materialize(files, tmp_path)
        except OSError:
            pass

    uninstall(tmp_path)

    assert not (
        tmp_path / MANIFEST_NAME
    ).exists(), "Manifest file should not exist after rollback-via-uninstall"


def test_failed_install_leaves_no_manifest(tmp_path):
    """If materialize() raises before saving the manifest, no manifest file is written."""
    files = {
        "agent.md": "# agent",
        "extra.md": "# extra",
    }

    call_count = {"n": 0}
    original_write_text = Path.write_text

    def patched_write_text(self, data, encoding=None, errors=None):
        call_count["n"] += 1
        if call_count["n"] == 2:
            raise OSError("Simulated disk failure on write #2")
        if encoding is not None and errors is not None:
            return original_write_text(self, data, encoding, errors)
        if encoding is not None:
            return original_write_text(self, data, encoding)
        return original_write_text(self, data)

    with patch.object(Path, "write_text", patched_write_text):
        with pytest.raises(OSError):
            materialize(files, tmp_path)

    manifest_path = tmp_path / MANIFEST_NAME
    assert (
        not manifest_path.exists()
    ), "No manifest should exist after a failed materialize"


def test_uninstall_without_manifest_returns_empty(tmp_path):
    """uninstall() on a dir with no manifest is a no-op and returns []."""
    result = uninstall(tmp_path)
    assert result == []


def test_rollback_exceptions_logged_to_stderr(capsys, monkeypatch):
    """If uninstall() raises during rollback, the error is logged to stderr."""
    import install_cli.orchestrate as orchestrate

    # Make materialize succeed (adds dest to written_dests), then materialize_flows raise
    # so the except block is entered and uninstall is attempted.
    call_count = {"n": 0}

    def fake_materialize(files, _dest, **_kwargs):
        call_count["n"] += 1
        return list(files.keys())

    def fake_materialize_flows(_dest, **_kwargs):
        raise OSError("simulated mid-install failure")

    def fake_uninstall(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(orchestrate, "materialize", fake_materialize)
    monkeypatch.setattr(orchestrate, "materialize_flows", fake_materialize_flows)
    monkeypatch.setattr(orchestrate, "uninstall", fake_uninstall)

    with pytest.raises(OSError):
        orchestrate._run_host("claude", dry_run=False, repair=False, force=False)

    captured = capsys.readouterr()
    assert "[pathly rollback error]" in captured.err
