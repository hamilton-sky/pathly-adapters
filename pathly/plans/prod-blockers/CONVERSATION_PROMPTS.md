# prod-blockers — Conversation Guide

Split into 4 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Quick fixes — traceback leak, deprecated datetime, subprocess timeout (Phases 1.1-1.3)

**Stories delivered:** S1.1, S1.2, S1.3

**Prompt to paste:**
```
Read pathly/plans/prod-blockers/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement prod-blockers Conversation 1 (Phases 1.1-1.3) from pathly/plans/prod-blockers/IMPLEMENTATION_PLAN.md.

**Pre-flight:** Before editing anything, run `python -m pytest tests/ -x -q` and record the output in pathly/plans/prod-blockers/PROGRESS.md under a `## Baseline` section. This establishes the pre-existing failure baseline.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/http_server.py` — remove traceback from 500 handlers; add logging.exception()
- `src/pathly_orchestrator/fsm.py` — replace datetime.utcnow(); add timeout=30 + TimeoutExpired handling

Scope:
- Phase 1.1: In `http_server.py`, ensure `import logging` is present. In both `/next_action` and `/complete_stage` except blocks, replace the `import traceback` + `traceback.format_exc()` pattern with `logging.exception(...)`. Return only `{"error": str(e), "type": type(e).__name__}` with HTTP 500.
- Phase 1.2: In `fsm.py` line 15, change `from datetime import datetime` to `from datetime import datetime, timezone`. On line 354, change `datetime.utcnow().isoformat()` to `datetime.now(timezone.utc).isoformat()`. Do not touch `eventlog.py`.
- Phase 1.3: In `fsm.py` lines 264-269, add `timeout=30` to the `git add -A` subprocess.run() call and wrap in try/except subprocess.TimeoutExpired — raise RuntimeError("git add timed out after 30 seconds"). Apply identical treatment to the `git commit` call on lines 274-279. Ensure a timeout on git add prevents git commit from executing.

Architectural rules to observe:
- Read CLAUDE.md and any .claude/rules/ files for project-specific rules before implementing.
- Stay within `http_server.py` and `fsm.py`. Do not touch any other files except to add the import.
- Do not change any behavior other than what is specified above.

Do NOT touch: `eventlog.py`, `materialize.py`, any test files, any other orchestrator files.

Verify: `python -m pytest tests/ -x -q`

After done, update pathly/plans/prod-blockers/PROGRESS.md phases 1.1-1.3 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout src/pathly_orchestrator/http_server.py src/pathly_orchestrator/fsm.py` and retry.
```

**Expected output:** `http_server.py` 500 handlers return no traceback; `fsm.py` emits no deprecation warning; both git subprocess calls have timeout guards.

**Files touched:** `src/pathly_orchestrator/http_server.py`, `src/pathly_orchestrator/fsm.py`

---

## Conversation 2: Manifest integrity (Phase 2.1)

**Stories delivered:** S2.1

**Prompt to paste:**
```
Read pathly/plans/prod-blockers/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement prod-blockers Conversation 2 (Phase 2.1) from pathly/plans/prod-blockers/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/install_cli/materialize.py` — add manifest version + SHA-256 hash on write; validate on load; abort uninstall on missing files

Scope:
- Phase 2.1: Add `import hashlib` and `import json` if not already present. Define a module-level helper `_hash_files_dict(files: dict) -> str` that computes `hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()`.
  - `_save_manifest()`: before writing, add `"_manifest_version": "1"` and `"_manifest_hash": _hash_files_dict(manifest["files"])` to the manifest dict.
  - `_load_manifest()`: after reading, if `"_manifest_version"` is absent, raise `ValueError("Manifest missing _manifest_version field")`. Recompute hash from `data["files"]`; if mismatch, raise `ValueError("Manifest hash mismatch — file may be corrupted or tampered")`. Do NOT silently fall back to `{"files": {}}` on these errors — only fall back on `json.JSONDecodeError` or `FileNotFoundError`.
  - `uninstall()`: before the deletion pass, collect all manifest entry paths that are not found on disk. If any are missing, print a warning listing them and return without deleting, unless `confirm_manifest=True` is passed. Map `--confirm-manifest` CLI flag to this parameter.

Architectural rules to observe:
- Read CLAUDE.md and any .claude/rules/ files for project-specific rules before implementing.
- Stay within `materialize.py`. Do not change `_load_manifest()`'s fallback for `json.JSONDecodeError` or `FileNotFoundError` — only add the version/hash checks.
- The hash must be computed over the `files` sub-dict only, not the entire manifest dict (which would include the hash itself).

Do NOT touch: `http_server.py`, `fsm.py`, any test files, any other install CLI files.

Verify: `python -m pytest tests/ -x -q`

After done, update pathly/plans/prod-blockers/PROGRESS.md phase 2.1 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout src/install_cli/materialize.py` and retry.
```

**Expected output:** Manifests written by `_save_manifest()` carry `_manifest_version` and `_manifest_hash`; `_load_manifest()` raises `ValueError` on missing version or hash mismatch; `uninstall()` aborts on orphaned manifest entries.

**Files touched:** `src/install_cli/materialize.py`

---

## Conversation 3: SSE hardening — path traversal + thread leak (Phases 3.1-3.2)

**Stories delivered:** S3.1, S3.2

**Prompt to paste:**
```
Read pathly/plans/prod-blockers/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement prod-blockers Conversation 3 (Phases 3.1-3.2) from pathly/plans/prod-blockers/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/http_server.py` — resolve + boundary-check project_root; stop tailer threads on last client disconnect

Scope:
- Phase 3.1: After reading `project_root = request.args.get('project_root', '')`, call `resolved_root = Path(project_root).resolve()`. Construct `events_path = (resolved_root / 'pathly' / 'plans' / topic / 'EVENTS.jsonl').resolve()`. Call `events_path.is_relative_to(resolved_root)` — if False, return `jsonify({"error": "Invalid project_root"}), 400` immediately. Use `resolved_root` (not the raw string) in subsequent calls within this handler.
- Phase 3.2: In the `generate()` function's `finally` block, after removing `client_q` from `_clients[key]`, check `if not _clients[key]`. If the list is now empty: pop `key` from `_tailers` (capturing the stop event), call `stop_evt.set()`, and del `_clients[key]` to free memory. If `_clients` and `_tailers` are mutated from multiple threads without a lock, add `_lock = threading.Lock()` at module level and guard the finally block with it. Check whether a lock already exists before adding one.

Architectural rules to observe:
- Read CLAUDE.md and any .claude/rules/ files for project-specific rules before implementing.
- Stay within `http_server.py`. Do not modify `_tail_events` logic beyond what is needed for the stop event to be honored.
- A second client disconnecting while a first remains connected must NOT stop the tailer thread — verify this logic is correct.

Do NOT touch: `fsm.py`, `materialize.py`, any test files, `eventlog.py`.

Verify: `python -m pytest tests/ -x -q`

After done, update pathly/plans/prod-blockers/PROGRESS.md phases 3.1-3.2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout src/pathly_orchestrator/http_server.py` and retry.
```

**Expected output:** `/events/stream` returns 400 for path-traversal `project_root` values; tailer threads are stopped and removed from `_tailers` when the last client disconnects.

**Files touched:** `src/pathly_orchestrator/http_server.py`

---

## Conversation 4: Tests — rollback and manifest validation (Phases 4.1-4.2)

**Stories delivered:** S4.1, S4.2

**Prompt to paste:**
```
Read pathly/plans/prod-blockers/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement prod-blockers Conversation 4 (Phases 4.1-4.2) from pathly/plans/prod-blockers/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists. Read tests/conftest.py and tests/test_setup.py to understand the custom tmp_path fixture and existing test patterns before writing any test code.

**Codebase files this conversation touches:**
- `tests/test_rollback.py` — CREATE: test that a mid-loop write failure leaves no orphaned files
- `tests/test_manifests.py` — CREATE: parametrized test asserting required fields in all 3 manifest JSON files

Scope:
- Phase 4.1: Create `tests/test_rollback.py`. Use the custom `tmp_path` fixture from `tests/conftest.py` (not pytest's built-in). Use `monkeypatch` to patch `Path.write_text` with a wrapper that raises `OSError` on call N=2 (so the first write succeeds, the second fails). Call `materialize()` (or the relevant install entry point) with a minimal setup pointing at `tmp_path`. Assert no install files remain in `tmp_path` after the exception. Follow the `@pytest.mark.parametrize` + `patch` patterns from `tests/test_setup.py`.
- Phase 4.2: Create `tests/test_manifests.py`. Parametrize over 3 manifest paths, resolved from the repo root using `Path(__file__).parent.parent / ...`. For each: load JSON, assert `name` is `str`, `version` is `str`, `description` is `str`, `author` is `(str, dict)`, `skills` is `list`. Use `pytest.mark.parametrize` with IDs from the filename stem. A missing field must cause test failure, not a pass or skip.

  Manifest paths:
  - `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`
  - `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`
  - `src/pathly_data/adapters/claude/.claude-plugin/marketplace.json`

Architectural rules to observe:
- Read CLAUDE.md and any .claude/rules/ files for project-specific rules before implementing.
- Use the project's custom tmp_path fixture — never pytest's built-in tmp_path.
- All paths in tests must be resolved relative to the repo root or `__file__`, never hardcoded absolute paths.

Do NOT touch: `http_server.py`, `fsm.py`, `materialize.py`, `conftest.py`, any existing test files.

Verify: `python -m pytest tests/ -x -q`

After done, update pathly/plans/prod-blockers/PROGRESS.md phases 4.1-4.2 to DONE and set overall status to COMPLETE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with `git checkout tests/test_rollback.py tests/test_manifests.py` and retry.
```

**Expected output:** Both new test files are collected by pytest; all tests pass; `tests/test_manifests.py` parametrizes over 3 manifest files; `tests/test_rollback.py` verifies no orphaned files after a failed install.

**Files touched:** `tests/test_rollback.py`, `tests/test_manifests.py`
