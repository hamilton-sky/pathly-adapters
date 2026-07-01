# prod-blockers — Implementation Plan

## Overview

This plan fixes seven production-blocking issues in the Pathly orchestrator and install CLI: a traceback leak in HTTP 500 responses, a deprecated datetime call in `fsm.py`, missing subprocess timeouts, no manifest integrity verification, path-traversal exposure in the SSE stream endpoint, orphaned tailer threads, and missing automated tests for rollback and manifest field validation. All changes are surgical — no new abstractions are introduced. The codebase must remain runnable after every conversation.

## Layer Architecture

```
HTTP layer  (http_server.py)   →   orchestration logic  (fsm.py)   →   install CLI  (materialize.py)
      ↓                                     ↓                                  ↓
  Conv 1 (error leak)             Conv 1 (datetime, timeout)           Conv 2 (manifest integrity)
  Conv 3 (SSE hardening)                                                Conv 4 (tests)
```

---

## Pre-flight (before Conversation 1 begins)

Run the full test suite and record all pre-existing failures as the baseline. Do not fix pre-existing failures unless they are caused by one of the issues in this plan.

```
python -m pytest tests/ -x -q 2>&1 | tee pathly/plans/prod-blockers/baseline_failures.txt
```

Record the result in `pathly/plans/prod-blockers/PROGRESS.md` under a `## Baseline` section before any edits are made.

---

## Phases

### Phase 1.1: Strip traceback from 500 responses   ← Conversation: 1

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY: remove `traceback.format_exc()` from both exception handlers

**Done when:** Neither the `/next_action` nor `/complete_stage` 500 handler includes `"traceback"` in its JSON response, and both call `logging.exception()` to log the full traceback to stderr.

**Delivers stories:** S1.1

**Depends on:** nothing

**Enables:** Phase 1.2

**Details:**
- At the top of the file, ensure `import logging` is present.
- In the `except Exception` block for `/next_action` (lines 96-102): replace the `import traceback` + `traceback.format_exc()` pattern with `logging.exception("next_action error")`. Return `jsonify({"error": str(e), "type": type(e).__name__}), 500`.
- Apply the identical change to the `/complete_stage` handler (lines 129-135).
- Do not change any other behavior of these handlers.

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 1.2: Replace deprecated datetime.utcnow()   ← Conversation: 1

**File:** `src/pathly_orchestrator/fsm.py` — MODIFY: update datetime import and replace deprecated call

**Done when:** The string `datetime.utcnow` does not appear in `fsm.py`, and `timezone` is imported alongside `datetime`.

**Delivers stories:** S1.2

**Depends on:** Phase 1.1 (same conversation, sequential)

**Enables:** Phase 1.3

**Details:**
- Line 15: change `from datetime import datetime` to `from datetime import datetime, timezone`.
- Line 354: change `datetime.utcnow().isoformat()` to `datetime.now(timezone.utc).isoformat()`.
- Do not touch `eventlog.py` — it already uses the correct form.

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 1.3: Add timeout to subprocess git calls   ← Conversation: 1

**File:** `src/pathly_orchestrator/fsm.py` — MODIFY: add `timeout=30` and catch `TimeoutExpired`

**Done when:** Both `subprocess.run()` calls in the git-commit logic include `timeout=30`, and a `subprocess.TimeoutExpired` catch block raises `RuntimeError` for each.

**Delivers stories:** S1.3

**Depends on:** Phase 1.2

**Enables:** Conversation 2

**Details:**
- Lines 264-269 (`git add -A`): add `timeout=30` to the `subprocess.run()` call. Wrap in a try/except for `subprocess.TimeoutExpired`; raise `RuntimeError("git add timed out after 30 seconds")`.
- Lines 274-279 (`git commit`): add `timeout=30`. Wrap similarly; raise `RuntimeError("git commit timed out after 30 seconds")`.
- The `TimeoutExpired` catch must be placed so that a timeout on `git add` prevents `git commit` from being called.

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 2.1: Manifest integrity — write, read, and uninstall guard   ← Conversation: 2

**File:** `src/install_cli/materialize.py` — MODIFY: add hash+version on write, validate on load, abort on missing files in uninstall

**Done when:** `_save_manifest()` writes `_manifest_version` and `_manifest_hash`; `_load_manifest()` raises `ValueError` on missing version or hash mismatch; `uninstall()` aborts (without deleting) when a manifest entry is missing from disk unless `--confirm-manifest` is passed.

**Delivers stories:** S2.1

**Depends on:** Conversation 1 complete

**Enables:** Conversation 3

**Details:**
- Add `import hashlib, json` if not already present.
- Define a helper `_hash_files_dict(files: dict) -> str` that returns `hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest()`.
- `_save_manifest()` (lines 268-272): after building the manifest dict, add `manifest["_manifest_version"] = "1"` and `manifest["_manifest_hash"] = _hash_files_dict(manifest["files"])` before writing.
- `_load_manifest()` (lines 258-265): after reading, check for `_manifest_version` key — if absent, raise `ValueError("Manifest missing _manifest_version field")`. Recompute hash from `data["files"]`; if it does not match `data["_manifest_hash"]`, raise `ValueError("Manifest hash mismatch — file may be corrupted or tampered")`.
- `uninstall()` (lines 336-379): before the deletion loop, check each entry path. If any do not exist on disk, print a warning listing the missing paths and return without deleting unless the caller passes `confirm_manifest=True` (which maps to the `--confirm-manifest` CLI flag).

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 3.1: Path-traversal guard in `/events/stream`   ← Conversation: 3

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY: resolve and boundary-check the events path

**Done when:** A request to `/events/stream` with a `project_root` whose resolved events path escapes the resolved `project_root` returns HTTP 400 before any file is opened.

**Delivers stories:** S3.1

**Depends on:** Conversation 2 complete

**Enables:** Phase 3.2

**Details:**
- Line 144: after reading `project_root = request.args.get('project_root', '')`, call `resolved_root = Path(project_root).resolve()`.
- Before passing to `_tail_events`, construct `events_path = resolved_root / 'pathly' / 'plans' / topic / 'EVENTS.jsonl'` and call `.resolve()` on it.
- Check `events_path.is_relative_to(resolved_root)`. If False, return `jsonify({"error": "Invalid project_root"}), 400`.
- Pass `resolved_root` (not the raw string) downstream where `project_root` was previously used in this handler.

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 3.2: Stop tailer threads when last client disconnects   ← Conversation: 3

**File:** `src/pathly_orchestrator/http_server.py` — MODIFY: add cleanup logic in the `generate()` finally block

**Done when:** When the last client for a `(project_root, topic)` key disconnects, the entry is removed from `_tailers` and `stop_evt.set()` is called. A subsequent connection for the same key starts a fresh thread.

**Delivers stories:** S3.2

**Depends on:** Phase 3.1

**Enables:** Conversation 4

**Details:**
- Lines 169-173 (`finally` block in `generate()`): after removing `client_q` from `_clients[key]`, check `if not _clients[key]`. If true: pop `key` from `_tailers` (store as `stop_evt`) and call `stop_evt.set()`. Also remove the empty list from `_clients` to prevent memory growth.
- Use a threading lock if `_clients` and `_tailers` are mutated from multiple threads — check whether one already exists in the file and use it; if not, add `_lock = threading.Lock()` and guard the finally block.

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 4.1: Rollback test   ← Conversation: 4

**File:** `tests/test_rollback.py` — CREATE

**Done when:** `pytest tests/test_rollback.py -v` collects and passes at least one test that monkeypatches `Path.write_text` to fail on the Nth call and asserts no files remain in `tmp_path` afterward.

**Delivers stories:** S4.1

**Depends on:** Conversation 3 complete

**Enables:** Phase 4.2

**Details:**
- Use the custom `tmp_path` fixture from `tests/conftest.py`.
- Use `monkeypatch` to replace `Path.write_text` with a wrapper that raises `OSError` on call number N (choose N=2 so at least one file is written first).
- Call `materialize()` (or the relevant install entry point) with a minimal fixture setup pointing at `tmp_path`.
- Assert that no files from the install set exist under `tmp_path` after the exception is caught.
- Follow the `@pytest.mark.parametrize` + `patch` patterns from `tests/test_setup.py`.

**Verify:** `python -m pytest tests/ -x -q`

---

### Phase 4.2: Manifest field validation test   ← Conversation: 4

**File:** `tests/test_manifests.py` — CREATE

**Done when:** `pytest tests/test_manifests.py -v` collects 3 parametrized test cases (one per manifest file) and all pass against the current manifests.

**Delivers stories:** S4.2

**Depends on:** Phase 4.1

**Enables:** nothing (final phase)

**Details:**
- Parametrize over the 3 absolute paths (resolved from the repo root using `Path(__file__).parent.parent / ...`):
  - `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`
  - `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`
  - `src/pathly_data/adapters/claude/.claude-plugin/marketplace.json`
- For each: load JSON, assert `name` is `str`, `version` is `str`, `description` is `str`, `author` is `(str, dict)`, `skills` is `list`.
- Use `pytest.mark.parametrize` with IDs derived from the filename stem.

**Verify:** `python -m pytest tests/ -x -q`

---

## Prerequisites

- Python environment with all dependencies installable.
- `git` available on PATH.
- All 3 manifest JSON files exist at the paths listed above.

## Key Decisions

- **No rollback implementation in Conv 2** — the plan adds integrity detection (hash + version) and a guard in `uninstall()`, but does not implement write-rollback in `materialize()` itself; that is flagged as a known limitation in EDGE_CASES.md.
- **`timeout=30` chosen for git calls** — matches typical CI timeout conventions; not configurable in this plan to keep scope minimal.
- **Threading lock for SSE cleanup** — if no lock exists in `http_server.py`, one must be added; this is a correctness requirement, not an optimization.
