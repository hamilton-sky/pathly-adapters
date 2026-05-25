import pathly_telemetry.storage as storage_mod


def test_activity_rotates_at_5mb(tmp_path, monkeypatch):
    activity_file = tmp_path / "activity.jsonl"
    # Write a file just over 5 MB
    activity_file.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    monkeypatch.setattr(storage_mod, "ACTIVITY_FILE", activity_file)
    storage_mod.append_activity(agent="tester", feature="test", summary="rotation check")
    bak = activity_file.with_suffix(".jsonl.bak")
    assert bak.exists(), "Backup file should be created when size > 5 MB"
    assert activity_file.exists(), "New activity file should be created after rotation"
    # The new file should only contain the single new entry
    lines = activity_file.read_text().strip().splitlines()
    assert len(lines) == 1
