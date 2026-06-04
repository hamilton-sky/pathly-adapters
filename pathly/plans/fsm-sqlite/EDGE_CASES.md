---
name: Edge Cases
---
# fsm-sqlite — Edge Cases

## Category 1: Concurrency

### EC-1.1: Supervisor and FSM server append events simultaneously
- **Trigger**: Studio run is active; supervisor and the HTTP FSM server both call `append_event()` at the same moment
- **Current behavior**: `eventlog._APPEND_LOCK` guards threading; supervisor bypasses it (direct file write) → race on Windows (no fcntl)
- **Expected behavior**: SQLite WAL + `BEGIN IMMEDIATE` serializes all writes; no interleaving
- **Handled in**: Phase 1 (db.py `append_event` uses `BEGIN IMMEDIATE`) + Phase 4 (supervisor calls `eventlog.append_event`)

### EC-1.2: Two processes open the same pathly.db (HTTP server + supervisor)
- **Trigger**: both processes call `get_db(feature_dir)` for the same feature
- **Current behavior**: N/A (file-based, no shared state)
- **Expected behavior**: SQLite WAL allows concurrent reads; writer serialized by WAL lock; no `SQLITE_BUSY` error
- **Handled in**: Phase 1 (`PRAGMA journal_mode=WAL` in `get_db()`) — WAL handles this natively; no extra locking needed at Python level

### EC-1.3: Connection cache used from multiple threads
- **Trigger**: `http_server.py` (SSE thread) and `supervisor.py` (monitor thread) both call `get_db()` with `check_same_thread=False`
- **Current behavior**: N/A
- **Expected behavior**: `_cache_lock` protects cache initialization; `check_same_thread=False` allows cross-thread reuse; writes still serialized by SQLite WAL
- **Handled in**: Phase 1 (db.py `_cache_lock` + `check_same_thread=False`)

---

## Category 2: Process Crash and Recovery

### EC-2.1: Process crashes mid-write_state()
- **Trigger**: Python process killed between `execute()` and `commit()` in `write_state()`
- **Current behavior**: `.tmp` + rename gives atomicity; if crash after `.tmp` write but before rename → `.tmp` left on disk
- **Expected behavior**: SQLite rollback journal ensures uncommitted write is rolled back; no partial state in DB
- **Handled in**: Phase 3 (SQLite atomicity is automatic; no `.tmp` needed)

### EC-2.2: Process crashes mid-append_event()
- **Trigger**: crash between `execute()` and `commit()` in `append_event()`
- **Expected behavior**: uncommitted insert rolled back; event not in DB; next run retries from last known state
- **Handled in**: Phase 1 + Phase 3 (SQLite WAL rollback)

### EC-2.3: DB file locked by another process (SQLITE_BUSY)
- **Trigger**: another tool opens `pathly.db` with a long-running transaction while orchestrator writes
- **Expected behavior**: SQLite busy timeout; `get_db()` should set `conn.execute("PRAGMA busy_timeout=5000")` (5 second wait) before returning
- **Handled in**: Phase 1 — add `PRAGMA busy_timeout=5000` to `get_db()`

---

## Category 3: Backward Compatibility and Migration

### EC-3.1: Existing plan with STATE.json but no pathly.db
- **Trigger**: developer resumes an old feature after upgrading to fsm-sqlite version
- **Current behavior**: orchestrator reads STATE.json — works fine
- **Expected behavior**: `read_state()` falls back to STATE.json; `read_events()` falls back to EVENTS.jsonl; writes go to new `pathly.db`
- **Handled in**: Phase 3 (fallback `if pathly.db exists` guard) + Phase 8 (backward compat test fixture)

### EC-3.2: Migration script run twice (idempotency)
- **Trigger**: developer runs `migrate_to_sqlite.py` again on a feature that's already migrated
- **Expected behavior**: no duplicate events; script prints `events=0 (already migrated)` or similar
- **Handled in**: Phase 7 — UNIQUE constraint on `(feature, ts, type)` + `INSERT OR IGNORE`

### EC-3.3: Malformed JSONL line in legacy EVENTS.jsonl
- **Trigger**: a line in EVENTS.jsonl is truncated or corrupt (crash during write)
- **Expected behavior**: migration script skips the line with a warning; does not abort; remaining lines are imported
- **Handled in**: Phase 7 — `try/except json.JSONDecodeError` per line

### EC-3.4: Feature has both pathly.db AND legacy files
- **Trigger**: partial migration; migration script was interrupted
- **Expected behavior**: reads always use pathly.db (SQLite wins); legacy files ignored by Python layer
- **Handled in**: Phase 3 + Phase 8 (documented in test fixture)

---

## Category 4: SSE Stream Edge Cases

### EC-4.1: SSE client reconnects with Last-Event-ID
- **Trigger**: Studio browser disconnects and reconnects mid-stream
- **Expected behavior**: client sends `Last-Event-ID: 42`; server resumes from seq 43; no duplicate events
- **Handled in**: Phase 6 — `last_seq = int(request.headers.get("Last-Event-ID", 0))`

### EC-4.2: No events in DB yet (stream opened before first event)
- **Trigger**: Studio connects to SSE immediately after runner starts, before any events written
- **Expected behavior**: `read_events(since_seq=0)` returns `[]`; stream polls and blocks; delivers first event when it arrives
- **Handled in**: Phase 6 — poll sleep loop same as current; empty result = continue polling

### EC-4.3: EVENTS.jsonl rotated or truncated (legacy concern — eliminated)
- **Current behavior**: `_tail_events()` file-seek becomes invalid if file is truncated → misses events or crashes
- **Expected behavior**: N/A — SQLite seq numbers are monotonic and DB file is never truncated
- **Handled in**: Phase 6 (elimination of file-seek makes this impossible)

---

## Category 5: Schema Evolution

### EC-5.1: Future event type has extra fields
- **Trigger**: new code appends `{type: 'NEW_EVENT', extra_field: 'value', ...}` to `fsm_events`
- **Expected behavior**: full event JSON stored in `payload` column → no data loss; `type`, `ts`, `schema_version` extracted to columns for filtering
- **Handled in**: Phase 1 (payload = full JSON blob design decision)

### EC-5.2: New STATE.json field added by agent
- **Trigger**: agent writes `STATE.json` with a new field not in the `fsm_state` schema
- **Expected behavior**: field stored in `extra` JSON blob column; round-tripped through `read_state()` as-is
- **Handled in**: Phase 1 (`extra TEXT` column) + Phase 3 (`write_state()` maps known fields; remainder → extra)

---

## Known Limitations
- `PRAGMA synchronous=NORMAL` means OS crash (not process crash) could lose the last committed transaction. Acceptable: a lost AGENT_DONE event means the next run re-runs the same conversation — recoverable. Use `FULL` if strict durability is required (at ~2x write latency cost).
- One DB per feature folder: no cross-feature SQL joins. Cross-feature queries (e.g., "all features in BUILD") require iterating feature dirs and querying each DB. A future migration to a single central DB is possible but out of scope for this feature.
- `check_same_thread=False` on a cached connection means thread-safety relies on SQLite WAL + Python GIL. If Pathly ever uses `multiprocessing` (not just `threading`), a per-process connection is required.
