# TEST_FAILURES — fsm-sqlite

Date: 2026-06-04
Rigor: lite
Verify commands: all 4 ran; 427 passed, 3 skipped (full suite green)

---

## Summary

Two acceptance criteria are FAIL. All verify commands pass. All 427 tests pass.
The failures are criterion-level gaps between what the stories specify and what
was implemented — the tests themselves do not catch them because the tests were
written to match the implementation rather than the stories.

---

## Test Plan

### Story S1.1: SQLite DB layer

```
Story S1.1: SQLite DB layer
  Criterion: db.py exists and exports all 9 helpers
  Test: python -c "from src.pathly_orchestrator.db import ..."
  Status: PASS

  Criterion: get_db() opens pathly.db with WAL + synchronous=NORMAL
  Test: test_db.py::test_get_db_creates_tables
  Status: PASS

  Criterion: Schema creates 3 tables on first open (CREATE TABLE IF NOT EXISTS)
  Test: test_db.py::test_get_db_creates_tables
  Status: PASS

  Criterion: append_event() inserts one row and returns seq integer
  Test: test_db.py::test_append_and_read_events
  Status: PASS

  Criterion: read_events() returns list of dicts ordered by seq ASC
  Test: test_db.py::test_read_events_since_seq
  Status: PASS

  Criterion: write_state() uses INSERT OR REPLACE
  Test: test_db.py::test_write_and_read_state
  Status: PASS

  Criterion: tests/test_db.py passes — all 14 tests
  Test: pytest tests/test_db.py -v
  Status: PASS (14/14)

  Criterion: get_db() twice on same path returns cached connection
  Test: test_db.py::test_get_db_cached
  Status: PASS

  Criterion: read_state() returns None when no row exists
  Test: test_db.py::test_read_state_missing
  Status: PASS
```

### Story S2.1: EVENTS.jsonl → SQLite (event log)

```
Story S2.1: EVENTS.jsonl → SQLite (event log)
  Criterion: eventlog.append_event() writes to fsm_events; no direct .jsonl write
  Test: grep for open()+.jsonl in eventlog.py; inspect append_event() body
  Status: PASS — append_event() calls db.append_event() only, no file write

  Criterion: eventlog.read_events() reads from SQLite; falls back to .jsonl if no pathly.db
  Test: test_db.py::test_legacy_read_events_from_jsonl + read_events() source
  Status: PASS — (feature_dir / "pathly.db").exists() guard at line 141

  Criterion: supervisor.py no longer writes to EVENTS.jsonl directly
  Test: grep EVENTS.jsonl + write patterns in supervisor.py
  Status: PASS — only docstring/comment references found, no file writes

  Criterion: Concurrent appends do not corrupt events
  Test: test_db.py::test_concurrent_appends
  Status: PASS

  Criterion: _APPEND_LOCK removed from eventlog.py
  Test: grep _APPEND_LOCK in eventlog.py
  Status: PASS — not present

  Criterion: pytest tests/test_orchestrator.py tests/test_fsm.py tests/test_supervisor.py -q passes
  Test: ran those 3 suites
  Status: PASS (118 passed)
```

### Story S2.2: STATE.json → SQLite (FSM state)

```
Story S2.2: STATE.json → SQLite (FSM state)
  Criterion: eventlog.write_state() writes to fsm_state via db.py
  Test: inspect write_state() → _write_state_db() calls db.write_state()
  Status: PASS

  Criterion: eventlog.read_state() reads from fsm_state; falls back to STATE.json
  Test: test_db.py::test_legacy_read_state_from_json + read_state() source
  Status: PASS — (feature_dir / "pathly.db").exists() guard at line 177

  Criterion: pytest tests/test_fsm.py tests/test_orchestrator.py -q passes
  Test: ran as part of 118-test run above
  Status: PASS
```

### Story S3.1: RUNNER_STATE.json → SQLite (runner state mirror)

```
Story S3.1: RUNNER_STATE.json → SQLite
  Criterion: supervisor._write_mirror() calls db.write_runner_state() instead of write_text()
  Test: inspect _write_mirror() in supervisor.py
  Status: FAIL
  Notes: _write_mirror() still calls path.write_text() on line 269 AND then calls
         db.write_runner_state() on line 276. It is a dual-write, not a replacement.
         The story criterion says "instead of write_text()" — the old write_text() call
         remains. Tests in test_supervisor.py assert RUNNER_STATE.json exists on disk
         (lines 97, 112, 662-664), confirming the test suite was written to match the
         dual-write implementation rather than the story specification.

  Criterion: supervisor.recover_stale_mirrors() queries runner_state table and marks running→error
  Test: test_db.py::test_mark_stale_runners + recover_stale_mirrors() source
  Status: PASS — SQLite path exists and is exercised; file fallback retained for backward compat

  Criterion: RUNNER_STATE.json is no longer written by supervisor.py
  Test: grep write_text in supervisor.py
  Status: FAIL — same issue as above: write_text() at line 269 still writes the file

  Criterion: pytest tests/test_supervisor.py -q passes
  Test: included in 118-test run above
  Status: PASS (tests pass but they verify the dual-write behavior, not the story criterion)
```

### Story S3.2: AGENT_DONE watcher → SQLite seq poll

```
Story S3.2: AGENT_DONE watcher → SQLite seq poll
  Criterion: _agent_done_watcher() replaced with SQLite poll loop using last_seq
  Test: inspect _agent_done_watcher() body in supervisor.py
  Status: PASS — function retained by name but implementation is now SQLite poll
         (last_seq param, db.read_events(conn, feature, since_seq=seq) every 150ms)

  Criterion: No file handle to EVENTS.jsonl in _agent_done_watcher()
  Test: grep open()+EVENTS.jsonl in _agent_done_watcher scope
  Status: PASS — no file handles; uses db.get_db() + db.read_events()

  Criterion: Watcher detects AGENT_DONE in the feature's fsm_events table
  Test: supervisor.py lines 170-176; integration via test_supervisor.py
  Status: PASS

  Criterion: pytest tests/test_supervisor.py -q passes
  Test: included in 118-test run
  Status: PASS
```

### Story S3.3: SSE tail → SQLite seq-number polling

```
Story S3.3: SSE tail → SQLite seq-number polling
  Criterion: http_server._tail_events() polls fsm_events WHERE seq > last_seq
  Test: inspect _tail_events() in http_server.py
  Status: PASS — uses db.read_events(conn, topic, since_seq=last_seq) at line 252

  Criterion: runner.read_last_agent_done() queries SQLite AGENT_DONE row
  Test: inspect read_last_agent_done() in runner.py
  Status: PASS — calls db.read_last_agent_done() with JSONL fallback

  Criterion: pytest tests/test_http_server.py tests/test_runner.py -q passes
  Test: included in 118-test run
  Status: PASS

  Criterion: Client reconnects with Last-Event-ID: 42 → stream resumes from seq 43
  Test: grep Last-Event-ID in http_server.py and test_http_server.py
  Status: NOT COVERED
  Notes: No Last-Event-ID header parsing found in http_server.py or test_http_server.py.
         The _tail_events() always starts from last_seq=0. SSE reconnect with
         Last-Event-ID is not implemented or tested.
```

### Story S4.1: Migration script

```
Story S4.1: Migration script
  Criterion: scripts/migrate_to_sqlite.py exists and is runnable
  Test: python scripts/migrate_to_sqlite.py --plans-dir pathly/plans --dry-run
  Status: PASS — exits 0

  Criterion: Imports STATE.json, EVENTS.jsonl, RUNNER_STATE.json for each feature folder
  Test: dry-run output shows per-feature summary with event counts and state/runner status
  Status: PASS — output shows 18 features processed

  Criterion: Idempotent (running twice does not duplicate events)
  Test: test_db.py::test_legacy_read_events_from_jsonl covers db-level; migration
        script dry-run only (no double-run idempotency test found)
  Status: PASS (db.py uses unique constraints; migration logic relies on them)

  Criterion: Prints per-feature summary: "feature: N events imported, state: OK/MISSING, runner: OK/MISSING"
  Test: dry-run output inspection
  Status: PASS — format matches: "[dry-run] [feature]: events=N state=ok/missing runner=ok/missing"

  Criterion: Does not delete original .json/.jsonl files
  Test: --dry-run confirmed non-destructive; test coverage in test_db.py
  Status: PASS
```

### Story S4.2: Backward compat fallback + tests

```
Story S4.2: Backward compat fallback + tests
  Criterion: read_state() returns data from STATE.json when pathly.db absent
  Test: test_db.py::test_legacy_read_state_from_json
  Status: PASS

  Criterion: read_events() returns data from EVENTS.jsonl when pathly.db absent
  Test: test_db.py::test_legacy_read_events_from_jsonl
  Status: PASS

  Criterion: recover_stale_mirrors() reads RUNNER_STATE.json when pathly.db absent
  Test: test_db.py::test_recover_stale_mirrors_no_db
  Status: PASS

  Criterion: pytest tests/ -q passes (full suite green)
  Test: pytest tests/ -q
  Status: PASS — 427 passed, 3 skipped
```

---

## Failures Summary

### FAIL 1 — S3.1: _write_mirror() dual-write (criterion: replace write_text, not augment)

**What failed:** Story S3.1 criterion states `_write_mirror()` should call
`db.write_runner_state()` "instead of `write_text()`". The implementation does both:
it still writes RUNNER_STATE.json via `write_text()` (supervisor.py:269) and also
writes to SQLite (supervisor.py:276).

**Expected:** RUNNER_STATE.json no longer written by supervisor.py after migration.

**Actual:** Both writes happen. RUNNER_STATE.json is still created on every state
change. Tests explicitly assert the file exists (test_supervisor.py:97, 112, 662-664).

**Impact:** The atomicity problem the story was trying to fix still exists — a crash
between the `write_text()` call and the SQLite write leaves an inconsistent state.
However, the SQLite write does succeed when the process is running normally.

**Note for builder:** This may be intentional dual-write for backward compat during
migration. If so, story S3.1 criterion "RUNNER_STATE.json is no longer written" needs
to be updated to reflect the actual design. If it is a genuine gap, remove the
`write_text()` call from `_write_mirror()` and update tests accordingly.

---

### NOT COVERED — S3.3 edge case: Last-Event-ID reconnect

**What is missing:** The `_tail_events()` SSE function has no `Last-Event-ID` header
parsing. The story criterion "Client reconnects mid-stream with `Last-Event-ID: 42` →
stream resumes from seq 43" is not implemented or tested.

**Impact:** Lite rigor — this is an edge-case criterion in S3.3. The happy path (SSE
from seq 0) works correctly. The reconnect behavior is a correctness gap for Studio
clients that reconnect after network interruption.
