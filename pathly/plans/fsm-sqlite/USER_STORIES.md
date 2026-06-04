---
name: User Stories
---
# fsm-sqlite — User Stories

## Context

The Pathly FSM currently persists pipeline state across three plain files per feature:
`STATE.json` (FSM transitions), `EVENTS.jsonl` (append-only event log), and
`RUNNER_STATE.json` (Studio UI mirror). These files have three known failure modes:
(1) `STATE.json` can be partially written if the process crashes mid-rename;
(2) `EVENTS.jsonl` is written by both `eventlog.py` (with a threading lock) and
`supervisor.py` directly (without any lock), creating a race condition — especially
on Windows where `fcntl` is unavailable; (3) `RUNNER_STATE.json` uses a simple
`write_text()` call with no atomicity guarantee.

This feature replaces all three files with a SQLite database (`pathly.db`) per feature
folder, using WAL mode for concurrent readers and `BEGIN IMMEDIATE` transactions for
serialized writes. The markdown plan files (CONVERSATION_PROMPTS.md, USER_STORIES.md,
etc.) stay on disk — agents read them directly; only the orchestrator's control state
moves to SQLite.

---

## Stories

### Story S1.1: SQLite DB layer
**As a** Pathly orchestrator, **I want** a single `db.py` module that owns the SQLite
schema and all CRUD helpers, **so that** no other module writes raw JSON to disk for
FSM state.

**Acceptance Criteria:**
- [ ] `src/pathly_orchestrator/db.py` exists and exports: `get_db()`, `append_event()`, `read_events()`, `read_last_agent_done()`, `write_state()`, `read_state()`, `write_runner_state()`, `read_runner_state()`, `mark_stale_runners()`
- [ ] `get_db(feature_dir)` opens `<feature_dir>/pathly.db` with `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`
- [ ] Schema creates three tables on first open: `fsm_events`, `fsm_state`, `runner_state` (all with `CREATE TABLE IF NOT EXISTS`)
- [ ] `append_event()` inserts one row and returns the `seq` integer (auto-increment)
- [ ] `read_events(conn, feature, since_seq=0)` returns a list of dicts ordered by `seq ASC`
- [ ] `write_state()` uses `INSERT OR REPLACE` for atomic upsert
- [ ] `tests/test_db.py` passes: all helpers exercised, no file I/O outside `pathly.db`

**Edge Cases:**
- Calling `get_db()` twice on the same path returns a cached connection (no double-init)
- `read_state()` returns `None` when no row exists yet

**Delivered by:** Phase 1–2 → Conversation 1

---

### Story S2.1: EVENTS.jsonl → SQLite (event log)
**As a** Pathly orchestrator, **I want** all event appends to go through `db.py`
instead of direct file writes, **so that** EVENTS.jsonl race conditions are eliminated
and event ordering is enforced by the DB sequence number.

**Acceptance Criteria:**
- [ ] `eventlog.py:append_event()` writes to `fsm_events` table via `db.py`; no direct `.jsonl` file write
- [ ] `eventlog.py:read_events()` reads from `fsm_events` table; falls back to `.jsonl` if `pathly.db` does not exist (backward compat for old plans)
- [ ] `supervisor.py` no longer writes to EVENTS.jsonl directly — calls `eventlog.append_event()` instead
- [ ] Concurrent appends from supervisor thread and FSM thread do not corrupt events (verified by `test_db.py` concurrent insert test)
- [ ] `_APPEND_LOCK` in `eventlog.py` is removed (SQLite WAL + `BEGIN IMMEDIATE` replaces it)
- [ ] `pytest tests/test_orchestrator.py tests/test_fsm.py tests/test_supervisor.py -q` passes

**Edge Cases:**
- `read_events()` called before any events exist returns `[]`
- Malformed payload stored in DB is returned as-is (no silent drop)

**Delivered by:** Phase 3–4 → Conversation 2

---

### Story S2.2: STATE.json → SQLite (FSM state)
**As a** Pathly FSM engine, **I want** state transitions written atomically to SQLite,
**so that** a mid-transition crash cannot produce a partial `STATE.json`.

**Acceptance Criteria:**
- [ ] `eventlog.py:write_state()` writes to `fsm_state` table via `db.py`; no `.tmp` + rename pattern needed
- [ ] `eventlog.py:read_state()` reads from `fsm_state` table; falls back to `STATE.json` if `pathly.db` does not exist
- [ ] `STATE.json` is no longer written by the Python layer (agents using the Write tool are unaffected — they write STATE.json as a cache; the Python layer reads SQLite as authoritative)
- [ ] `pytest tests/test_fsm.py tests/test_orchestrator.py -q` passes

**Edge Cases:**
- `read_state()` for a brand-new feature (no DB yet) returns `None`
- Existing `STATE.json` on disk is ignored if `pathly.db` exists

**Delivered by:** Phase 3 → Conversation 2

---

### Story S3.1: RUNNER_STATE.json → SQLite (runner state mirror)
**As a** Studio UI, **I want** runner state written atomically so that a crash during
`_write_mirror()` cannot leave Studio reading partial JSON.

**Acceptance Criteria:**
- [ ] `supervisor.py:_write_mirror()` calls `db.write_runner_state()` instead of `write_text()`
- [ ] `supervisor.py:recover_stale_mirrors()` queries `runner_state` table and marks `status='running'` rows as `status='error'`
- [ ] `RUNNER_STATE.json` is no longer written by `supervisor.py`
- [ ] `pytest tests/test_supervisor.py -q` passes

**Edge Cases:**
- `recover_stale_mirrors()` called when no DB exists does nothing (no crash)
- `read_runner_state()` returns `None` for a feature with no prior run

**Delivered by:** Phase 5 → Conversation 3

---

### Story S3.2: AGENT_DONE watcher → SQLite seq poll
**As a** supervisor, **I want** to detect agent completion by polling the SQLite events
table instead of tailing EVENTS.jsonl, **so that** the watcher works correctly on
Windows and does not hold a file handle across the PTY lifetime.

**Acceptance Criteria:**
- [ ] `supervisor.py:_agent_done_watcher()` is replaced with a SQLite poll loop: records `last_seq` before spawning PTY; polls `db.read_events(conn, feature, since_seq=last_seq)` every ~150ms; signals on first AGENT_DONE row
- [ ] No file handle to EVENTS.jsonl opened in `_agent_done_watcher()` or equivalent function
- [ ] Watcher correctly detects AGENT_DONE in the same feature's `fsm_events` table
- [ ] `pytest tests/test_supervisor.py -q` passes

**Edge Cases:**
- PTY exits before AGENT_DONE is written → watcher times out after `timeout` seconds and raises (same behavior as before)
- Two concurrent runs for different features do not cross-signal (filter by feature column)

**Delivered by:** Phase 5b → Conversation 3

---

### Story S3.3: SSE tail → SQLite seq-number polling
**As a** Studio SSE consumer, **I want** the `/events` stream to read from SQLite by
sequence number instead of file-seeking EVENTS.jsonl, **so that** file rotation or
truncation cannot break the stream.

**Acceptance Criteria:**
- [ ] `http_server.py:_tail_events()` polls `fsm_events` table with `WHERE seq > :last_seq` instead of file seek
- [ ] `runner.py:read_last_agent_done()` queries `SELECT * FROM fsm_events WHERE type='AGENT_DONE' ORDER BY seq DESC LIMIT 1` instead of scanning lines
- [ ] SSE stream delivers events in `seq` order with no duplicates on reconnect
- [ ] `pytest tests/test_http_server.py tests/test_runner.py -q` passes

**Edge Cases:**
- Client reconnects mid-stream with `Last-Event-ID: 42` → stream resumes from seq 43
- No events in DB → stream blocks (poll with sleep, same as before)

**Delivered by:** Phase 6 → Conversation 3

---

---

### Story S4.1: Migration script for existing plans
**As a** developer with existing plans on disk, **I want** a one-shot script that
imports STATE.json, EVENTS.jsonl, and RUNNER_STATE.json into pathly.db, **so that**
existing features continue to work after upgrading.

**Acceptance Criteria:**
- [ ] `scripts/migrate_to_sqlite.py` exists and is runnable: `python scripts/migrate_to_sqlite.py [--plans-dir pathly/plans]`
- [ ] For each feature folder containing any of STATE.json, EVENTS.jsonl, RUNNER_STATE.json: imports into the feature's `pathly.db`
- [ ] Idempotent: running twice does not duplicate events (events table uses `UNIQUE(feature, seq_from_jsonl)` or skips if payload already exists)
- [ ] Prints a per-feature summary: `feature: N events imported, state: OK/MISSING, runner: OK/MISSING`
- [ ] Does not delete the original .json/.jsonl files (non-destructive)

**Edge Cases:**
- Feature folder with no .json/.jsonl files is silently skipped
- Malformed line in EVENTS.jsonl is logged as a warning and skipped

**Delivered by:** Phase 7 → Conversation 4

---

### Story S4.2: Backward compat fallback + tests
**As a** plan without a pathly.db yet, **I want** the orchestrator to fall back to
reading STATE.json and EVENTS.jsonl transparently, **so that** old plans are not broken
before migration is run.

**Acceptance Criteria:**
- [ ] `eventlog.py:read_state()` returns data from `STATE.json` when `pathly.db` does not exist
- [ ] `eventlog.py:read_events()` returns data from `EVENTS.jsonl` when `pathly.db` does not exist
- [ ] `supervisor.py:recover_stale_mirrors()` reads `RUNNER_STATE.json` when `pathly.db` does not exist
- [ ] `pytest tests/ -q` passes (full suite green)

**Edge Cases:**
- Feature has both `pathly.db` AND legacy files → SQLite wins; .json/.jsonl ignored

**Delivered by:** Phase 8 → Conversation 4
