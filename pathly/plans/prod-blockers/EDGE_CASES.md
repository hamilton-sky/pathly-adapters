# prod-blockers — Edge Cases

## Category 1: Error Response Handling (S1.1)

### EC-1.1: Exception message contains newlines or special characters
- **Trigger**: An unhandled exception whose `.args[0]` contains `\n`, `\t`, or non-ASCII characters.
- **Current behavior**: `str(e)` is serialized by `jsonify` — Flask handles JSON encoding, so this is safe.
- **Expected behavior**: Response body is valid JSON regardless of exception message content.
- **Handled in**: Phase 1.1 / Conv 1 — no special handling needed; `jsonify` encodes correctly.

### EC-1.2: Only one of the two endpoints is patched
- **Trigger**: Developer patches `/next_action` but overlooks `/complete_stage` (or vice versa).
- **Current behavior**: One endpoint still leaks tracebacks.
- **Expected behavior**: Both handlers must be patched in the same commit.
- **Handled in**: Phase 1.1 / Conv 1 — the prompt explicitly lists both endpoints; story S1.1 criterion covers both.

---

## Category 2: Datetime and Subprocess (S1.2, S1.3)

### EC-2.1: eventlog.py modified by mistake
- **Trigger**: Builder searches for `utcnow` project-wide and edits `eventlog.py`.
- **Current behavior**: `eventlog.py` already uses `datetime.now(timezone.utc)` — editing it is a no-op at best, a regression at worst.
- **Expected behavior**: Only `fsm.py` line 354 is changed.
- **Handled in**: Phase 1.2 / Conv 1 — prompt explicitly says do not touch `eventlog.py`.

### EC-2.2: git add times out, git commit still executes
- **Trigger**: `subprocess.TimeoutExpired` is caught after `git add`, but execution falls through to `git commit`.
- **Current behavior**: Undefined — git state is inconsistent.
- **Expected behavior**: `RuntimeError` is raised immediately on `git add` timeout; `git commit` is never called.
- **Handled in**: Phase 1.3 / Conv 1 — the try/except must be placed to break out of the sequence.

### EC-2.3: git call succeeds but returns non-zero exit code
- **Trigger**: `git add` or `git commit` completes within 30 seconds but fails (e.g., nothing to commit, locked index).
- **Current behavior**: Not in scope for this plan — existing return code handling (if any) is preserved.
- **Expected behavior**: Timeout fix does not change behavior for non-timeout failures.
- **Handled in**: Out of scope — only timeout handling is added.

---

## Category 3: Manifest Integrity (S2.1)

### EC-3.1: Old manifest (no _manifest_version) loaded after upgrade
- **Trigger**: An install was performed before this fix; the manifest file has no `_manifest_version`.
- **Current behavior**: After this fix, `_load_manifest()` raises `ValueError`.
- **Expected behavior**: `ValueError` is raised with a message identifying the missing field. The user must re-install or manually migrate the manifest.
- **Handled in**: Phase 2.1 / Conv 2 — `ValueError` is the intended behavior; a migration path is out of scope.

### EC-3.2: Empty files dict
- **Trigger**: A manifest is written with no installed files.
- **Current behavior**: After this fix, `_hash_files_dict({})` must produce a deterministic non-empty hash.
- **Expected behavior**: `json.dumps({}, sort_keys=True, separators=(",", ":"))` → `"{}"` → a valid SHA-256 hex digest.
- **Handled in**: Phase 2.1 / Conv 2 — no special case needed; the hash function handles this correctly.

### EC-3.3: Uninstall with partially-missing manifest entries
- **Trigger**: Some files in the manifest were manually deleted; uninstall detects the mismatch.
- **Current behavior**: After this fix, uninstall prints a warning and aborts unless `--confirm-manifest` is passed.
- **Expected behavior**: No files are deleted in the abort path; the user is given a list of missing entries to inspect.
- **Handled in**: Phase 2.1 / Conv 2 — the pre-deletion check collects all missing paths before aborting.

---

## Category 4: SSE Path Traversal (S3.1)

### EC-4.1: project_root is a symlink to an out-of-bounds directory
- **Trigger**: `project_root` points to a symlink whose resolved target is outside the intended boundary.
- **Current behavior**: `.resolve()` follows symlinks, so the resolved path will escape the boundary check.
- **Expected behavior**: The boundary check uses `.resolve()` on both paths, so the symlink target is what is compared. The request is rejected if the resolved target escapes.
- **Handled in**: Phase 3.1 / Conv 3 — `.resolve()` is applied before `.is_relative_to()`.

### EC-4.2: project_root query param is missing
- **Trigger**: Client calls `/events/stream` without a `project_root` param.
- **Current behavior**: `request.args.get('project_root', '')` returns `''`; `Path('').resolve()` returns the server's CWD.
- **Expected behavior**: The empty-string case should be handled — either with a 400 response or by the existing behavior (CWD). Builder should check the existing contract and not change it unless the resolved path fails the boundary check.
- **Handled in**: Phase 3.1 / Conv 3 — the boundary check will catch the case where the resolved events path escapes the resolved (CWD) root; behavior for valid empty-string case is preserved.

### EC-4.3: Python version < 3.9 (no Path.is_relative_to)
- **Trigger**: Server runs Python 3.8.
- **Current behavior**: `Path.is_relative_to()` does not exist; calling it raises `AttributeError`.
- **Expected behavior**: Builder must check the Python version constraint; use `str(events_path).startswith(str(resolved_root) + os.sep)` as fallback if needed.
- **Handled in**: ARCHITECTURE_PROPOSAL.md risk section — builder responsibility.

---

## Category 5: SSE Thread Lifecycle (S3.2)

### EC-5.1: Two clients disconnect simultaneously for the same key
- **Trigger**: Race condition — both threads check `if not _clients[key]` and both see an empty list.
- **Current behavior**: Without a lock, both could call `stop_evt.set()` and pop from `_tailers` — the second pop would raise `KeyError`.
- **Expected behavior**: A threading lock ensures only one thread performs the cleanup.
- **Handled in**: Phase 3.2 / Conv 3 — `_lock` guards the finally block.

### EC-5.2: New connection arrives during cleanup
- **Trigger**: A new client connects for the same key while the finally block is running cleanup.
- **Current behavior**: Without a lock, the new connection might create a new tailer before the old one is stopped, resulting in two tailers.
- **Expected behavior**: The lock ensures cleanup completes atomically before the new connection's setup runs.
- **Handled in**: Phase 3.2 / Conv 3 — same `_lock` must guard the new-connection setup path as well.

---

## Known Limitations

- **No write rollback in materialize()** — if `materialize()` fails mid-loop, previously written files are not removed. This plan adds detection and a test for this scenario (Conv 4, S4.1) but does not implement automatic rollback in the production code. Full rollback (e.g., copying files to a temp directory before writing, then atomically swapping) is out of scope for this plan.
- **Manifest migration** — existing installs with old manifests will fail the new integrity check. A migration utility is out of scope; users must re-install.
- **SSE load testing** — the threading lock correctness for high-concurrency scenarios is not covered by automated tests in this plan.
