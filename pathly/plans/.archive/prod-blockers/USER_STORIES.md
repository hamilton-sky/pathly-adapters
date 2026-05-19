# prod-blockers — User Stories

## Context

The Pathly orchestrator HTTP server and install CLI contain several production-blocking issues discovered during code review: internal stack traces leak to API clients, a deprecated datetime API produces warnings in Python 3.12+, subprocess calls have no timeout guard, the install manifest has no integrity protection, the SSE event stream constructs file paths without boundary checks, and tailer threads are never stopped when the last client disconnects. These issues collectively create security exposure, reliability risk, and upgrade friction before the product can be released. This plan fixes all of them in four focused conversations.

---

## Stories

### Story S1.1: Strip traceback from 500 responses

**As a** security engineer, **I want** HTTP 500 error responses to contain only the error message and type, **so that** internal stack traces are never exposed to API clients.

**Acceptance Criteria:**
- [ ] A request to `/next_action` that triggers a server-side exception returns a JSON body containing only `"error"` and `"type"` keys — no `"traceback"` key is present.
- [ ] A request to `/complete_stage` that triggers a server-side exception returns a JSON body containing only `"error"` and `"type"` keys — no `"traceback"` key is present.
- [ ] The full traceback is written to stderr via `logging.exception()` and is NOT present in the HTTP response body for either endpoint.
- [ ] A request with a deliberately bad payload that causes an unhandled exception causes `{"error": "<message>", "type": "<ExceptionClass>"}` to be returned with HTTP 500, and no traceback string appears in the response.

**Edge Cases:**
- Exception message itself contains newlines or special characters — must still serialize to valid JSON.
- Both endpoints must be patched; fixing only one is a failure.

**Delivered by:** Phase 1.1 → Conversation 1

---

### Story S1.2: Replace deprecated `datetime.utcnow()` in fsm.py

**As a** developer running Python 3.12+, **I want** `fsm.py` to use `datetime.now(timezone.utc)` instead of `datetime.utcnow()`, **so that** no deprecation warnings are emitted during orchestration.

**Acceptance Criteria:**
- [ ] The string `datetime.utcnow` does not appear anywhere in `src/pathly_orchestrator/fsm.py`.
- [ ] `timezone` is imported from the `datetime` module in `fsm.py`.
- [ ] Running `python -W error -c "from pathly_orchestrator import fsm"` exits with code 0 (no DeprecationWarning treated as error).

**Edge Cases:**
- `eventlog.py` already uses the correct form — do not touch it.

**Delivered by:** Phase 1.2 → Conversation 1

---

### Story S1.3: Add timeout to subprocess git calls in fsm.py

**As a** developer running automated orchestration, **I want** `git add` and `git commit` subprocess calls to have a 30-second timeout, **so that** a hung git process cannot block the orchestrator indefinitely.

**Acceptance Criteria:**
- [ ] Both `subprocess.run()` calls in `fsm.py` (git add and git commit) include `timeout=30`.
- [ ] When `subprocess.TimeoutExpired` is raised by either call, a `RuntimeError` is raised with a message that identifies which git operation timed out.
- [ ] `python -m pytest tests/ -x -q` passes after this change.

**Edge Cases:**
- Timeout on `git add` must not silently proceed to `git commit`.
- The `RuntimeError` message must be distinct enough to identify which call timed out.

**Delivered by:** Phase 1.3 → Conversation 1

---

### Story S2.1: Manifest integrity on write and read

**As a** developer using the install CLI, **I want** the install manifest to carry a version field and a SHA-256 hash of its contents, **so that** corruption or tampering is detected at load time rather than causing silent failures.

**Acceptance Criteria:**
- [ ] After `_save_manifest()` writes a manifest, the JSON file contains a `_manifest_version` field (value `"1"`) and a `_manifest_hash` field containing the SHA-256 hex digest of the canonical JSON of the `files` dict (keys sorted, no extra whitespace).
- [ ] `_load_manifest()` raises `ValueError` with a non-empty message when `_manifest_version` is absent from a loaded manifest.
- [ ] `_load_manifest()` raises `ValueError` with a non-empty message when the recomputed hash of the `files` dict does not match `_manifest_hash`.
- [ ] A manifest file where `_manifest_hash` has been changed to an arbitrary wrong value causes `_load_manifest()` to raise `ValueError`.
- [ ] `uninstall()` prints a clear warning and aborts (without deleting any files) when a manifest entry path is not found on disk, unless `--confirm-manifest` is passed.

**Edge Cases:**
- An old manifest with no `_manifest_version` field must fail with `ValueError`, not silently fall back to `{"files": {}}`.
- An empty `files` dict must still produce a deterministic, non-empty hash.

**Delivered by:** Phase 2.1 → Conversation 2

---

### Story S3.1: Reject path-traversal attempts in `/events/stream`

**As a** security engineer, **I want** the `/events/stream` endpoint to resolve `project_root` and verify the constructed events path stays within it, **so that** an attacker cannot read arbitrary files via path traversal.

**Acceptance Criteria:**
- [ ] A request to `/events/stream` with `project_root=../../etc` (or any value whose resolved events path escapes the resolved `project_root`) returns HTTP 400.
- [ ] A request with a valid `project_root` that contains the expected `pathly/plans/<topic>/EVENTS.jsonl` sub-path returns HTTP 200 (or begins streaming).
- [ ] The boundary check uses `.resolve()` on both `project_root` and the constructed path before comparison.

**Edge Cases:**
- `project_root` that is a symlink to a location outside the intended boundary must still be rejected after resolution.
- A missing `project_root` query param still returns a well-formed error response (400 or the existing default behavior).

**Delivered by:** Phase 3.1 → Conversation 3

---

### Story S3.2: Stop tailer threads when the last SSE client disconnects

**As a** server operator, **I want** SSE tailer threads to be stopped and removed from `_tailers` when the last client for a given key disconnects, **so that** long-running processes do not accumulate orphaned threads.

**Acceptance Criteria:**
- [ ] After the last client for a `(project_root, topic)` key disconnects, the corresponding entry is removed from `_tailers`.
- [ ] After the last client disconnects, `stop_evt.set()` is called on the tailer's stop event so the thread exits.
- [ ] A new connection for the same key after all prior clients have disconnected starts a fresh tailer thread (i.e., the old stopped thread is not reused).
- [ ] A second client disconnecting while a first client is still connected does NOT stop the tailer thread.

**Edge Cases:**
- Concurrent disconnects for the same key — only the thread that empties the client list must call `stop_evt.set()`.

**Delivered by:** Phase 3.2 → Conversation 3

---

### Story S4.1: Rollback test — no orphaned files after mid-install failure

**As a** developer maintaining the install CLI, **I want** a test that verifies no files are left behind when `materialize()` fails mid-loop, **so that** the rollback guarantee is machine-checked on every CI run.

**Acceptance Criteria:**
- [ ] `tests/test_rollback.py` exists and is collected by pytest without errors.
- [ ] The test uses `monkeypatch` to patch `Path.write_text` to raise `OSError` on the Nth write call (where N > 1 to allow at least one file to be written before failure).
- [ ] The test asserts that no files from the install exist in `tmp_path` after the failed `materialize()` call.
- [ ] The test uses the project's custom `tmp_path` fixture (from `tests/conftest.py`), not pytest's built-in.

**Edge Cases:**
- Test must not leave side effects in the real filesystem — all paths must be under `tmp_path`.

**Delivered by:** Phase 4.1 → Conversation 4

---

### Story S4.2: Parametrized test for required manifest JSON fields

**As a** developer maintaining plugin manifests, **I want** a parametrized pytest test that loads all 3 manifest JSON files and asserts required fields are present and correctly typed, **so that** a broken manifest is caught before deployment.

**Acceptance Criteria:**
- [ ] `tests/test_manifests.py` exists and is collected by pytest without errors.
- [ ] The test is parametrized over the 3 manifest file paths: `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`, `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`, and `src/pathly_data/adapters/claude/.claude-plugin/marketplace.json`.
- [ ] For each manifest, the test asserts: `name` is a `str`, `version` is a `str`, `description` is a `str`, `author` is a `str` or `dict`, `skills` is a `list`.
- [ ] A manifest file with any required field missing causes the test to fail (not pass or skip).

**Edge Cases:**
- File paths are relative to the repository root — the test must resolve them correctly regardless of where pytest is invoked from.

**Delivered by:** Phase 4.2 → Conversation 4
