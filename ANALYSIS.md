# Pathly Adapters — Code Review Analysis

Codebase: `pathly-adapters` v2.4.1  
Reviewer: Claude Code (automated deep review)  
Date: 2026-05-18  
Scope: All Python source in `src/`, existing docs cross-checked for accuracy

---

## Summary

The codebase is well-structured for its stage. The core/adapter separation is clean, the stitch pipeline is deterministic, and the atomic install with rollback is a genuinely good design. The issues below are real but not architectural — they are hardening gaps, consistency problems, and missing tests. None of them are blockers for a public beta; several are blockers before calling this production-ready.

---

## Issues and Solutions

### 1. Hook path validation is string-based (SECURITY · HIGH)

**File:** `src/pathly_hooks/classify_feedback.py:49–56`, `src/pathly_hooks/inject_feedback_ttl.py`

**Issue:** `inject_feedback_ttl.py` uses string-based path checking. A crafted path like `plans/../../etc/passwd` that contains a `feedback/` substring would pass the check if the string match is not canonicalized. `classify_feedback.py` uses `Path.resolve()` + `is_relative_to()` correctly, but `inject_feedback_ttl.py` may not.

**Solution:** Both hooks must resolve the path before any check:
```python
resolved = Path(raw_path).resolve()
plans_dir = (Path(project_root_env) / "plans").resolve()
if not resolved.is_relative_to(plans_dir):
    sys.exit(1)
```
Add unit tests for: path pointing outside `plans/`, symlink traversal, missing `PATHLY_PROJECT_ROOT`, malformed JSON payload.

---

### 2. Manifest integrity not verified on load (SECURITY · HIGH)

**File:** `src/install_cli/materialize.py`

**Issue:** The Pathly-owned-file manifest (`.pathly-manifest.json`) is read on disk but its integrity is not verified. An externally edited manifest can falsely list user-owned files, causing `--uninstall` to delete files Pathly never created.

**Solution:**
1. Add a checksum or version field to the manifest on write.
2. On load, detect unexpected fields or structurally invalid manifests and refuse to proceed, printing a warning.
3. `--uninstall` should require `--confirm-manifest` if any manifest entry is not found at its expected path (defensive against partial edits).

---

### 3. SSE endpoint trusts `project_root` parameter without validation (SECURITY · MEDIUM)

**File:** `src/pathly_orchestrator/http_server.py:143–148`

**Issue:** The `/events/stream` endpoint receives `project_root` as a raw query parameter string and passes it directly to `Path(project_root) / 'pathly' / 'plans' / topic / 'EVENTS.jsonl'`. No allowlist or canonicalization is applied. A caller who can reach the HTTP server can read any EVENTS.jsonl-named file under any path on disk.

**Note:** The default bind is `127.0.0.1` which limits attack surface, but it's still a path-traversal risk if anything proxies to this server.

**Solution:**
```python
# Resolve and confirm path stays under expected roots
allowed_root = Path(project_root).resolve()
events_path = (allowed_root / 'pathly' / 'plans' / topic / 'EVENTS.jsonl').resolve()
if not events_path.is_relative_to(allowed_root):
    return jsonify({'error': 'invalid path'}), 400
```

---

### 4. Traceback leaks in HTTP 500 responses (SECURITY/INFO · LOW)

**File:** `src/pathly_orchestrator/http_server.py:96–102`, `127–133`

**Issue:** Both POST endpoints return `traceback.format_exc()` in JSON 500 responses. For a localhost-only server this is low risk, but if the server is ever proxied or exposed, internal file paths and library internals leak to the client.

**Solution:** Log the traceback to stderr, return only `{"error": str(e), "type": type(e).__name__}` to the client:
```python
import traceback, logging
logging.exception("FSM error in /next_action")
return jsonify({"error": str(e), "type": type(e).__name__}), 500
```

---

### 5. `datetime.utcnow()` is deprecated (RELIABILITY · MEDIUM)

**File:** `src/pathly_orchestrator/fsm.py:354`

**Issue:** `datetime.utcnow()` has been deprecated since Python 3.12 and emits a `DeprecationWarning`. It also returns a naive datetime (no timezone info), which can cause silent bugs if timestamps are ever compared.

**Solution:**
```python
from datetime import datetime, timezone
event["ts"] = datetime.now(timezone.utc).isoformat()
```

---

### 6. Git subprocess in `run_transition_actions` has no timeout (RELIABILITY · MEDIUM)

**File:** `src/pathly_orchestrator/fsm.py:264–288`

**Issue:** `subprocess.run(["git", "add", "-A"], ...)` and `subprocess.run(["git", "commit", ...])` have no `timeout` parameter. If git blocks (e.g., credential prompt, network repo, locked index), the FSM hangs indefinitely.

**Solution:**
```python
subprocess.run(
    ["git", "add", "-A"],
    cwd=str(project_root),
    capture_output=True,
    text=True,
    timeout=30,
)
```
Catch `subprocess.TimeoutExpired` and raise as `RuntimeError`.

---

### 7. Broad `except Exception` in CLI modules (RELIABILITY · LOW)

**Files:** `src/pathly_orchestrator/back_cli.py:~90`, `src/pathly_orchestrator/ff_cli.py:~116`

**Issue:** Bare `except Exception as e: print(e); sys.exit(1)` swallows tracebacks that would help diagnose real bugs. It also catches `KeyboardInterrupt` in some Python versions if the hierarchy is wrong.

**Solution:** Either use specific exceptions (`ValueError`, `OSError`, `FileNotFoundError`) or re-raise unexpected ones:
```python
except (ValueError, OSError) as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
```

---

### 8. EVENTS.jsonl malformed-line handling is silent (RELIABILITY · LOW)

**Files:** `src/pathly_orchestrator/eventlog.py`, `src/pathly_orchestrator/http_server.py:58–62`

**Issue:** Both the event log reader and the SSE tailer assume every line in EVENTS.jsonl is valid JSON. A single corrupt line (e.g., from a partial write or killed process) causes `json.loads` to raise and either crash or silently skip all subsequent events.

**Solution:** Wrap each line's `json.loads` in a try/except and log corrupt lines to stderr:
```python
for raw in f:
    raw = raw.strip()
    if not raw:
        continue
    try:
        yield json.loads(raw)
    except json.JSONDecodeError:
        logging.warning("Corrupt EVENTS.jsonl line skipped: %r", raw[:80])
```

---

### 9. Path-discovery code is duplicated across CLI modules (MAINTAINABILITY · LOW)

**Files:** `src/pathly_orchestrator/back_cli.py`, `src/pathly_orchestrator/ff_cli.py`, `src/pathly_orchestrator/status_cli.py`, `src/pathly_orchestrator/log_cli.py`

**Issue:** The `_SCAN_ROOTS` constant and `_find_most_recent_state` / `_find_topic_dir` patterns are repeated across CLI modules. When a new flow type is added (e.g., `pathly/spikes`), it must be added in every module.

**Solution:** Extract to a shared internal module:
```
src/pathly_orchestrator/_discovery.py
  SCAN_ROOTS = [...]
  def find_most_recent_state(cwd) -> ...
  def find_topic_dir(cwd, topic) -> ...
```
All CLI modules import from `_discovery`.

---

### 10. `classify_feedback.py` hardcodes model name indirectly (MAINTAINABILITY · MEDIUM)

**File:** `src/pathly_hooks/classify_feedback.py`

**Issue:** The hook uses a regex heuristic to classify questions (no LLM call in the version reviewed). However, the module docstring says it "may call the Anthropic API when `ANTHROPIC_API_KEY` is present" — implying a prior or future version uses a hardcoded model name that becomes a compatibility dependency at release time.

**Solution:** If an LLM call is added, read the model name from an environment variable with a sensible default:
```python
MODEL = os.environ.get("PATHLY_CLASSIFY_MODEL", "claude-haiku-4-5-20251001")
```
Document the variable in README under "Environment variables."

---

### 11. No retry logic for network operations in Studio installer (RELIABILITY · LOW)

**File:** `src/pathly_studio_cli/install.py`

**Issue:** The GitHub Release download uses `urllib` with 15–120 second timeouts but no retry. A transient network failure gives a hard error with no recovery option.

**Solution:** Add a simple retry loop (3 attempts, exponential backoff) around the download:
```python
for attempt in range(3):
    try:
        urllib.request.urlretrieve(url, dest)
        break
    except urllib.error.URLError:
        if attempt == 2:
            raise
        time.sleep(2 ** attempt)
```

---

### 12. No CI schema validation for plugin manifests (TESTING · MEDIUM)

**Files:** `src/pathly_data/adapters/claude/.claude-plugin/plugin.json`, `src/pathly_data/adapters/codex/.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`

**Issue:** CI currently only checks that manifests parse as valid JSON. It does not validate against the actual plugin schema (required fields, types, enum values). A mis-typed field will silently pass CI and only fail when a user installs.

**Solution:** Add a schema validation step in CI:
```yaml
- name: Validate plugin manifests
  run: python -m pytest tests/test_manifests.py
```
Test: each manifest has required fields, all referenced skill names exist as installed files after a dry-run.

---

### 13. No end-to-end rollback test (TESTING · HIGH)

**File:** `src/install_cli/materialize.py`

**Issue:** Atomic install with rollback is a key safety guarantee, but there is no test that verifies partial-failure rollback. If a future change breaks the rollback path, it will silently regress.

**Solution:** Add a pytest fixture that patches `Path.write_text` to fail on the Nth file, then asserts that no files were written to the temp home directory.

---

### 14. `update_progress` in `run_transition_actions` uses fragile string replace (RELIABILITY · LOW)

**File:** `src/pathly_orchestrator/fsm.py:317–319`

**Issue:** `content.replace(f"| {conv} |", f"| {conv} | DONE |", 1)` will silently do nothing if the expected table row format changes. There is no error if the replacement produces no change, making it impossible to distinguish "already marked" from "format changed."

**Solution:** Check if the replacement actually changed the content and log a warning if not:
```python
new_content = content.replace(...)
if new_content == content:
    logging.warning("update_progress: no row matched conv=%d in PROGRESS.md", conv)
else:
    progress_file.write_text(new_content, encoding="utf-8")
```

---

### 15. SSE tailer threads are never cleaned up (RESOURCE LEAK · LOW)

**File:** `src/pathly_orchestrator/http_server.py:150–156`

**Issue:** When a `(topic, project_root)` combination is first requested, a daemon tailer thread is started and stored in `_tailers`. The thread is never stopped, even when all SSE clients for that key disconnect. For a long-lived server with many different topics, this accumulates dead threads.

**Solution:** In `generate()`'s `finally` block, check if the client list for the key is now empty and set `_tailers[key]`:
```python
finally:
    with _lock:
        lst = _clients.get(key, [])
        if client_q in lst:
            lst.remove(client_q)
        if not lst:
            stop_evt = _tailers.pop(key, None)
            if stop_evt:
                stop_evt.set()
```

---

## Production Readiness Blockers

Items that must be resolved before calling v3.0 production-ready:

| # | Issue | Priority |
|---|-------|----------|
| 2 | Manifest integrity not verified | HIGH |
| 1 | Hook path validation (inject_feedback_ttl) | HIGH |
| 13 | No rollback regression test | HIGH |
| 12 | No manifest schema validation in CI | MEDIUM |
| 5 | `datetime.utcnow()` deprecation | MEDIUM |
| 6 | Git subprocess no timeout | MEDIUM |

Items that are hardening recommendations (can ship beta without them):

| # | Issue | Priority |
|---|-------|----------|
| 3 | SSE project_root path traversal | MEDIUM |
| 4 | Traceback in 500 responses | LOW |
| 9 | CLI path-discovery duplication | LOW |
| 15 | SSE tailer thread leak | LOW |
| 7 | Broad except in CLI | LOW |
| 8 | EVENTS.jsonl corrupt-line handling | LOW |
| 14 | PROGRESS.md silent no-op | LOW |
| 11 | No retry in Studio installer | LOW |
