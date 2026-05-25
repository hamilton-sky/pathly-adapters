# TEST_FAILURES — security-hardening

Generated: 2026-05-25

---

## NOT COVERED: S3 — storage.py rotation logic

**Criterion:** `storage.py` rotates `activity.jsonl` to `activity.jsonl.bak` when the file exceeds 5 MB

**Gap:** No test exercises the rotation branch. The logic exists at `src/pathly_telemetry/storage.py` lines 24–25 but is untested.

**Suggested test (file: tests/test_storage.py):**
```python
def test_activity_rotates_at_5mb(tmp_path, monkeypatch):
    activity_file = tmp_path / "activity.jsonl"
    # Write a file just over 5 MB
    activity_file.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
    monkeypatch.setattr("pathly_telemetry.storage.ACTIVITY_FILE", activity_file)
    from pathly_telemetry.storage import append_activity
    append_activity(agent="tester", feature="test", summary="rotation check")
    bak = activity_file.with_suffix(".jsonl.bak")
    assert bak.exists(), "Backup file should be created when size > 5 MB"
    assert activity_file.exists(), "New activity file should be created after rotation"
    # The new file should only contain the single new entry
    lines = activity_file.read_text().strip().splitlines()
    assert len(lines) == 1
```

---

## NOT COVERED: S6 — materialize.py manifest hash mismatch raises RuntimeError

**Criterion:** `materialize.py` catches `ValueError` from `_load_manifest` and re-raises as `RuntimeError("Manifest integrity check failed: <path> — use --force to bypass")`

**Gap:** No test verifies the `RuntimeError` is raised when `_manifest_hash` is tampered. The logic exists at `src/install_cli/materialize.py` lines 30–33 but is untested.

**Additional discrepancy:** The criterion specifies the message format as:
  `"Manifest integrity check failed: <path> — use --force to bypass"`
  
  The actual message is:
  `f"Manifest integrity check failed for {dest}: {e} — use --force to bypass"`
  
  The word `for` is present and the ValueError text `{e}` appears after the path, which is extra. This is a minor format deviation from the spec — confirm with builder whether the spec should be updated to match, or the code should match the spec.

**Suggested test (file: tests/test_setup.py or tests/test_materialize.py):**
```python
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
```

---

## NOT COVERED: S6 — Rollback swallowed exceptions logged to stderr

**Criterion:** Rollback swallowed exceptions in `setup_command.py` are logged to stderr, not silently eaten.

**Gap:** Code inspection confirms stderr logging at `src/install_cli/setup_command.py` lines 278–279 and 283–284 (`print(f"[pathly rollback error] {e}", file=sys.stderr)`). However, no automated test verifies this behavior — a test must trigger a rollback failure and assert on stderr output.

**Suggested test (file: tests/test_rollback.py):**
```python
def test_rollback_exceptions_logged_to_stderr(tmp_path, capsys, monkeypatch):
    # Simulate a rollback where uninstall raises an exception
    import install_cli.setup_command as sc
    monkeypatch.setattr(sc, "uninstall", lambda *a, **kw: (_ for _ in ()).throw(OSError("disk full")))
    # Trigger an install that fails and rolls back
    # ... (depends on test harness for main())
    captured = capsys.readouterr()
    assert "rollback error" in captured.err
```

---

## NOTE: Pre-existing test failures (unrelated to security-hardening)

The following 5 tests are failing in the current suite and are NOT related to security-hardening acceptance criteria. They are reported here for visibility only — the builder should investigate separately:

1. `tests/test_fsm.py::test_append_event_preserves_other_fields` — ValueError
2. `tests/test_fsm_ops.py::test_complete_stage_after_planning` — ValueError
3. `tests/test_fsm_ops.py::test_complete_stage_with_valid_decision` — ValueError
4. `tests/test_fsm_ops.py::test_complete_stage_with_invalid_decision` — ValueError
5. `tests/test_setup.py::test_dry_run_real_codex_includes_plugin_manifest` — assertion mismatch
