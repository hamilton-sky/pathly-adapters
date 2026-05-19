# prod-blockers — Happy Flow

## Overview

A developer runs the Pathly orchestrator in production after all four conversations are complete. A builder agent triggers a next action, the orchestrator processes it cleanly without leaking internals, git operations complete within their timeout window, the SSE event stream safely delivers events to a single client, and the client disconnects cleanly — leaving no orphaned threads. Separately, a user installs a plugin, the manifest is written with integrity metadata, and a later uninstall verifies the manifest before touching any files.

---

## Step-by-Step Happy Flow

### Step 1: Builder calls /next_action — exception path

- **User does**: Sends a POST to `/next_action` with a payload that triggers a server-side exception (e.g., a missing required field).
- **System does**: The except block calls `logging.exception()` to write the full traceback to stderr. Returns `{"error": "<message>", "type": "<ExceptionClass>"}` with HTTP 500. No traceback in the response body.
- **State after**: The client sees a clean error object. The server log contains the full traceback for debugging.

### Step 2: Orchestrator writes a stage event

- **User does**: A stage completes; the orchestrator writes an event timestamp.
- **System does**: `fsm.py` calls `datetime.now(timezone.utc).isoformat()` — no deprecation warning emitted.
- **State after**: Event is written with a timezone-aware ISO timestamp. No `DeprecationWarning` in server output.

### Step 3: Orchestrator commits a git snapshot

- **User does**: Orchestration logic triggers a git add + commit.
- **System does**: Both `subprocess.run()` calls include `timeout=30`. git completes in under 30 seconds. No exception is raised.
- **State after**: Git commit succeeds. Orchestrator continues normally.

### Step 4: Plugin install with integrity manifest

- **User does**: Runs the install CLI to install a plugin.
- **System does**: `_save_manifest()` writes the manifest with `_manifest_version: "1"` and `_manifest_hash` set to the SHA-256 of the files dict. File is written to disk.
- **State after**: Manifest file on disk contains version and hash. Any subsequent load will validate against these values.

### Step 5: Manifest loaded for a subsequent operation

- **User does**: A follow-up CLI operation calls `_load_manifest()`.
- **System does**: Reads the manifest, checks `_manifest_version` is present, recomputes hash from `files`, confirms it matches `_manifest_hash`. Returns the manifest normally.
- **State after**: Manifest is trusted. Operation proceeds.

### Step 6: Client connects to /events/stream

- **User does**: A monitoring client connects to `/events/stream?project_root=/valid/path&topic=my-topic`.
- **System does**: `project_root` is resolved. The constructed events path is verified to be within the resolved root. A tailer thread is started and registered in `_tailers`. The client receives the SSE stream.
- **State after**: Tailer thread is running. `_clients[key]` contains the client queue. `_tailers[key]` contains the stop event.

### Step 7: Client disconnects

- **User does**: The monitoring client disconnects.
- **System does**: The `generate()` finally block removes the client queue from `_clients[key]`. The list is now empty. The block pops the stop event from `_tailers`, calls `stop_evt.set()`, and deletes `_clients[key]`.
- **State after**: Tailer thread receives the stop signal and exits. `_tailers` and `_clients` have no entry for this key. No orphaned thread remains.

---

## End State

After all four conversations are complete: 500 responses are safe for external consumption, the orchestrator runs without deprecation warnings on Python 3.12+, git operations are timeout-guarded, the install manifest carries integrity metadata, the SSE endpoint is safe from path traversal, tailer threads are properly lifecycle-managed, and two new test files provide automated regression coverage for rollback and manifest field validation.

## Success Indicators

- [ ] `grep -r "traceback" src/pathly_orchestrator/http_server.py` returns no matches inside except blocks.
- [ ] `grep "utcnow" src/pathly_orchestrator/fsm.py` returns no matches.
- [ ] Both `subprocess.run()` calls in `fsm.py` include `timeout=30`.
- [ ] A manifest written by `_save_manifest()` contains `_manifest_version` and `_manifest_hash` keys.
- [ ] `python -m pytest tests/ -x -q` passes with the two new test files collected.
