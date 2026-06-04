---
name: Implementation Plan
---
# fsm-sqlite — Implementation Plan

## Overview

Replace the three per-feature filesystem state files (`STATE.json`, `EVENTS.jsonl`,
`RUNNER_STATE.json`) with a single SQLite database (`pathly.db`) per feature folder.
The new `db.py` module owns all schema and CRUD logic. Existing Python callers
(`eventlog.py`, `supervisor.py`, `http_server.py`, `runner.py`) are updated to use
`db.py` instead of raw file I/O. Markdown plan files and agent-written documents stay
on disk — only the orchestrator's control plane state moves to SQLite.

## Layer Architecture

```
FSM HTTP server / supervisor.py / runner.py   (orchestrator control plane)
        │  calls
        ▼
eventlog.py  (state + event helpers — existing API preserved)
        │  calls
        ▼
db.py  (NEW — SQLite schema owner, WAL mode, all CRUD)
        │  opens
        ▼
pathly/plans/<feature>/pathly.db   (one DB per feature, WAL journal)
```

Agent-written files (STATE.json written by Write tool) continue to exist on disk.
Python layer reads SQLite as authoritative; STATE.json is treated as an agent cache.

---

## SQLite Schema

### Table: `fsm_events`  (replaces EVENTS.jsonl)
```sql
CREATE TABLE IF NOT EXISTS fsm_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    feature      TEXT    NOT NULL,
    type         TEXT    NOT NULL,
    ts           TEXT    NOT NULL,
    schema_version INTEGER DEFAULT 1,
    payload      TEXT    NOT NULL   -- full JSON blob (all event fields)
);
CREATE INDEX IF NOT EXISTS idx_events_feature ON fsm_events(feature, seq);
```

### Table: `fsm_state`  (replaces STATE.json)
```sql
CREATE TABLE IF NOT EXISTS fsm_state (
    feature             TEXT PRIMARY KEY,
    current             TEXT NOT NULL,
    rigor               TEXT,
    current_conversation INTEGER,
    retry_count_by_key  TEXT,   -- JSON blob
    iteration_by_stage  TEXT,   -- JSON blob
    updated_at          TEXT NOT NULL,
    conv_start_sha      TEXT,
    convs_total         INTEGER,
    convs_done          INTEGER,
    build_baseline      TEXT,   -- JSON blob
    extra               TEXT    -- JSON blob for forward-compat unknown fields
);
```

### Table: `runner_state`  (replaces RUNNER_STATE.json)
```sql
CREATE TABLE IF NOT EXISTS runner_state (
    feature         TEXT PRIMARY KEY,
    topic           TEXT,
    flow            TEXT,
    project_root    TEXT,
    model           TEXT,
    timeout         INTEGER,
    run_id          TEXT,
    status          TEXT    DEFAULT 'idle',
    current_state   TEXT    DEFAULT '',
    current_adapter TEXT,
    iterations      INTEGER DEFAULT 0,
    max_iterations  INTEGER,
    cost_usd_so_far REAL    DEFAULT 0.0,
    max_cost_usd    REAL,
    autonomy        TEXT    DEFAULT '{}',  -- JSON blob
    pending_menu    TEXT,                  -- JSON blob
    error_kind      TEXT,
    open_session    TEXT,                  -- JSON blob
    updated_at      TEXT
);
```

---

## Phases

### Phase 0: Pre-flight   ← Conversation: 1
**File:** `tests/` (read-only — run tests, record baseline)
**Done when:** `pytest tests/ -q` output is captured and any pre-existing failures are recorded in `pathly/plans/fsm-sqlite/PREFLIGHT.md`.
**Delivers stories:** —
**Depends on:** nothing
**Enables:** Phase 1 (establishes baseline so new failures from db.py are attributable)
**Details:**
- Run `pytest tests/ -q --tb=no` and note which tests fail before any changes.
- Run `python -c "import sqlite3; print(sqlite3.sqlite_version)"` to confirm sqlite3 stdlib is available.
- Record both outputs in `pathly/plans/fsm-sqlite/PREFLIGHT.md`.
**Verify:** `python -c "import sqlite3; print('ok')"` prints `ok`

---

### Phase 1: Create db.py   ← Conversation: 1
**File:** `src/pathly_orchestrator/db.py` — CREATE
**Done when:** `from pathly_orchestrator.db import get_db, append_event, read_events, write_state, read_state, write_runner_state, read_runner_state, mark_stale_runners, read_last_agent_done` succeeds without ImportError.
**Delivers stories:** S1.1
**Depends on:** Phase 0 (pre-flight baseline)
**Enables:** Phase 2 (tests), Phase 3 (eventlog migration)
**Details:**
- Module-level `_conn_cache: dict[str, sqlite3.Connection]` + `_cache_lock: threading.Lock` — one cached connection per absolute DB path.
- `get_db(feature_dir: Path) -> sqlite3.Connection` — opens `<feature_dir>/pathly.db`, sets WAL + NORMAL sync, runs `_init_schema()`, caches result.
- `_init_schema(conn)` — runs all three `CREATE TABLE IF NOT EXISTS` + index statements.
- `append_event(conn, feature, event_dict) -> int` — `INSERT INTO fsm_events`; returns `lastrowid` (the `seq`).
- `read_events(conn, feature, since_seq=0) -> list[dict]` — `SELECT payload FROM fsm_events WHERE feature=? AND seq>? ORDER BY seq ASC`; each row parsed from JSON, with `seq` injected.
- `read_last_agent_done(conn, feature) -> dict | None` — `SELECT payload FROM fsm_events WHERE feature=? AND type='AGENT_DONE' ORDER BY seq DESC LIMIT 1`.
- `write_state(conn, feature, state_dict)` — `INSERT OR REPLACE INTO fsm_state` using column-per-field mapping; JSON-encode dict fields.
- `read_state(conn, feature) -> dict | None` — `SELECT * FROM fsm_state WHERE feature=?`; reconstruct dict, JSON-decode blob fields; return `None` if no row.
- `write_runner_state(conn, feature, runner_dict)` — `INSERT OR REPLACE INTO runner_state`.
- `read_runner_state(conn, feature) -> dict | None` — `SELECT * FROM runner_state WHERE feature=?`; return `None` if no row.
- `mark_stale_runners(conn) -> int` — `UPDATE runner_state SET status='error' WHERE status='running'`; returns rowcount.
- All writes use `conn.execute()` + `conn.commit()`. No explicit transaction needed for single inserts (autocommit after commit). For `mark_stale_runners` use explicit `BEGIN IMMEDIATE`.
**Verify:** `python -c "from pathly_orchestrator.db import get_db; print('ok')"` prints `ok`

---

### Phase 2: test_db.py   ← Conversation: 1
**File:** `tests/test_db.py` — CREATE
**Done when:** `pytest tests/test_db.py -v` passes all tests with no errors.
**Delivers stories:** S1.1 (acceptance criterion: tests pass)
**Depends on:** Phase 1 (db.py must exist)
**Enables:** Phases 3–6 (regression guard for all later migrations)
**Details:**
- Use `tmp_path` pytest fixture for DB path — no real plan folders touched.
- Tests to write:
  - `test_get_db_creates_tables` — open DB, verify all three tables exist via `sqlite_master`.
  - `test_get_db_cached` — call `get_db()` twice on same path, assert `is` same connection object.
  - `test_append_and_read_events` — append 3 events, `read_events()` returns all 3 in seq order.
  - `test_read_events_since_seq` — append 5 events, `read_events(since_seq=3)` returns events 4 and 5.
  - `test_read_last_agent_done` — append mixed events including 2 AGENT_DONE; verify last one returned.
  - `test_write_and_read_state` — write state dict, read back, verify round-trip.
  - `test_read_state_missing` — `read_state()` on empty DB returns `None`.
  - `test_write_and_read_runner_state` — write runner dict, read back, verify round-trip.
  - `test_mark_stale_runners` — insert two 'running' rows and one 'done', call `mark_stale_runners()`, verify both 'running' become 'error', 'done' unchanged.
  - `test_concurrent_appends` — two threads each append 50 events; assert 100 rows, no `seq` gaps.
**Verify:** `pytest tests/test_db.py -v` — all tests green

---

### Phase 3: Migrate eventlog.py (events + state)   ← Conversation: 2
**File:** `src/pathly_orchestrator/eventlog.py` — MODIFY
**Done when:** `pytest tests/test_orchestrator.py tests/test_fsm.py -q` passes and no `.jsonl` or `.json` file writes occur during the test run (verify with a `tmp_path` fixture that checks `pathly.db` was created).
**Delivers stories:** S2.1, S2.2
**Depends on:** Phase 2 (db.py + tests exist)
**Enables:** Phase 4 (supervisor direct-write fix), Phase 6 (SSE tail refactor)
**Details:**

**For `append_event()`:**
- Resolve `feature_dir` from the existing `_resolve_path()` helper (keep it).
- Call `db.get_db(feature_dir)` to get connection.
- Call `db.append_event(conn, feature_name, event_dict)`.
- Remove `_APPEND_LOCK` threading lock (SQLite WAL replaces it).
- Remove `fcntl` import and all `flock` calls.
- Remove direct file open/write to `.jsonl`.

**For `read_events()`:**
- If `(feature_dir / "pathly.db").exists()`: call `db.read_events(conn, feature_name)`.
- Else (backward compat): read `.jsonl` file line-by-line as before.

**For `write_state()`:**
- Remove the `.tmp` + `os.fsync()` + atomic rename pattern.
- Call `db.write_state(conn, feature_name, state_dict)`.
- Keep validation logic (transition rules) unchanged — only the persistence layer changes.

**For `read_state()`:**
- If `pathly.db` exists: call `db.read_state(conn, feature_name)`.
- Else: read `STATE.json` from disk as before.

**Schema injection (CANDIDATE-006):**
Event fields written by eventlog.py:
- `STATE_TRANSITION`: `{type, to, ts, schema_version}`
- `PHASE_START/DONE`: `{type, phase, agent, feature, ts, schema_version}`
- `GATE_FAILED`: `{type, gate, transition, schema_version, ts}`
- `FEEDBACK_RESOLVED`: `{type, file, schema_version, ts}`
All fields stored as JSON in `payload` column; `type` and `ts` also extracted to top-level columns.

**Verify:** `pytest tests/test_orchestrator.py tests/test_fsm.py tests/test_storage.py -q`

---

### Phase 4: Fix supervisor.py direct EVENTS writes   ← Conversation: 2
**File:** `src/pathly_orchestrator/supervisor.py` — MODIFY
**Done when:** grep for direct `.jsonl` open/write in `supervisor.py` returns 0 matches; `pytest tests/test_supervisor.py -q` passes.
**Delivers stories:** S2.1 (eliminates the bypass that caused the race condition)
**Depends on:** Phase 3 (eventlog.py must already use SQLite)
**Enables:** Phase 5 (runner state migration)
**Details:**
- Find all locations where supervisor.py opens or writes `EVENTS.jsonl` directly (scout found lines ~205-206 and ~411-417).
- Replace each with a call to `eventlog.append_event(feature, event_dict)`.
- Import `eventlog` at top of `supervisor.py` if not already imported.
- Do NOT change any business logic — only the persistence call.
**Verify:** `grep -n "EVENTS.jsonl\|\.jsonl" src/pathly_orchestrator/supervisor.py` returns 0 lines; `pytest tests/test_supervisor.py -q` passes

---

### Phase 5: Migrate supervisor.py RUNNER_STATE   ← Conversation: 3
**File:** `src/pathly_orchestrator/supervisor.py` — MODIFY
**Done when:** grep for `RUNNER_STATE.json` write in supervisor.py returns 0 matches; `pytest tests/test_supervisor.py -q` passes.
**Delivers stories:** S3.1
**Depends on:** Phase 4 (supervisor.py cleaned up for events)
**Enables:** Phase 6 (http_server.py SSE)
**Details:**
- `_write_mirror(runner_dict)` → call `db.write_runner_state(conn, feature, runner_dict)`. Get `conn` from `db.get_db(feature_dir)`. Remove `write_text()` call.
- `recover_stale_mirrors()` → query `db.mark_stale_runners(conn)` on all DB paths found under `pathly/plans/*/pathly.db`. If no DB found for a feature dir, fall back to reading `RUNNER_STATE.json` and rewriting it as before.
- `read_runner_state()` (if it exists) → `db.read_runner_state(conn, feature)`.
**Verify:** `pytest tests/test_supervisor.py tests/test_runner_endpoints.py -q`

---

### Phase 5b: Replace _agent_done_watcher() with SQLite poll   ← Conversation: 3
**File:** `src/pathly_orchestrator/supervisor.py` — MODIFY
**Done when:** `_agent_done_watcher()` (or its replacement) contains no file open/read calls to EVENTS.jsonl; `pytest tests/test_supervisor.py -q` passes.
**Delivers stories:** S3.2
**Depends on:** Phase 5 (runner_state in SQLite; supervisor already imports db)
**Enables:** Phase 6 (all file-tail patterns eliminated from supervisor)
**Details:**
- Before spawning the PTY for a stage, capture `last_seq`:
  ```python
  conn = db.get_db(feature_dir)
  result = conn.execute(
      "SELECT MAX(seq) FROM fsm_events WHERE feature=?", (feature,)
  ).fetchone()
  last_seq = result[0] or 0
  ```
- Replace the file-tail loop in `_agent_done_watcher()` with:
  ```python
  deadline = time.monotonic() + timeout
  while time.monotonic() < deadline:
      rows = db.read_events(conn, feature, since_seq=last_seq)
      for event in rows:
          if event["type"] == "AGENT_DONE":
              return event
          last_seq = event["seq"]
      time.sleep(0.15)
  raise TimeoutError(f"No AGENT_DONE for {feature} within {timeout}s")
  ```
- Filter by `feature` column — prevents cross-feature signal if two runs are active.
- Keep timeout behavior identical to current implementation.
- Remove any import of `fcntl` or file-open logic in this function.
**Verify:** `pytest tests/test_supervisor.py -q` passes; `grep -n "EVENTS.jsonl" src/pathly_orchestrator/supervisor.py` returns 0

---

### Phase 6: Migrate http_server.py SSE tail + runner.py   ← Conversation: 3
**File:** `src/pathly_orchestrator/http_server.py` — MODIFY
**File:** `src/pathly_orchestrator/runner.py` — MODIFY
**Done when:** `pytest tests/test_http_server.py tests/test_runner.py -q` passes; no file-seek logic remains in `_tail_events()`.
**Delivers stories:** S3.2
**Depends on:** Phase 5 (runner state in SQLite)
**Enables:** Phase 7 (migration script can now safely replace files)
**Details:**

**http_server.py `_tail_events()`:**
- Replace file-open + seek pattern with: `last_seq = 0` (or from `Last-Event-ID` header); loop: `events = db.read_events(conn, feature, since_seq=last_seq)`; yield each as SSE; update `last_seq`; sleep poll.
- Honor `Last-Event-ID` header for reconnection: parse as integer, pass as `since_seq`.
- SSE format: `id: {seq}\ndata: {payload}\n\n`.

**runner.py `read_last_agent_done()`:**
- Replace line-scan loop with: `return db.read_last_agent_done(conn, feature)`.

**Verify:** `pytest tests/test_http_server.py tests/test_runner.py tests/test_runner_endpoints.py -q`

---

### Phase 7: Migration script   ← Conversation: 4
**File:** `scripts/migrate_to_sqlite.py` — CREATE
**Done when:** `python scripts/migrate_to_sqlite.py --dry-run` runs without error on the current `pathly/plans/` tree and prints a per-feature summary.
**Delivers stories:** S4.1
**Depends on:** Phase 6 (SQLite layer complete; db.py API stable)
**Enables:** Phase 8 (backward compat confirmed by running migration on test fixtures)
**Details:**
- CLI: `python scripts/migrate_to_sqlite.py [--plans-dir PATH] [--dry-run]`
- For each subdirectory of `plans-dir` that is not `.archive`:
  - Open (or create) `<feature>/pathly.db` via `db.get_db()`.
  - If `EVENTS.jsonl` exists: read each line, parse JSON, call `db.append_event()` if `type` not already in DB for that feature (idempotent guard: check `payload` content or use INSERT OR IGNORE with a unique constraint on `(feature, ts, type)`).
  - If `STATE.json` exists and no `fsm_state` row for feature: call `db.write_state()`.
  - If `RUNNER_STATE.json` exists and no `runner_state` row for feature: call `db.write_runner_state()`.
  - Print: `[feature]: events=N state=ok|missing runner=ok|missing`.
- `--dry-run`: print what would be imported without writing to DB.
- Malformed JSONL lines: log warning, skip, continue.
- Does not delete original files.

**Idempotent events guard:** Add `UNIQUE(feature, ts, type)` constraint to `fsm_events` with `INSERT OR IGNORE`. Note: `ts` is not guaranteed unique per feature — if duplicate (ts, type) possible, use a migration-specific column `migrated_from_line INT` instead.

**Verify:** `python scripts/migrate_to_sqlite.py --plans-dir pathly/plans --dry-run` exits 0; `python scripts/migrate_to_sqlite.py --plans-dir pathly/plans` then `python -c "import sqlite3; c=sqlite3.connect('pathly/plans/skill-notebook-editor/pathly.db'); print(c.execute('SELECT count(*) FROM fsm_events').fetchone())"` returns a positive count.

---

### Phase 8: Backward compat fallback + full test suite   ← Conversation: 4
**File:** `src/pathly_orchestrator/eventlog.py` — MODIFY (finalize fallback paths)
**File:** `src/pathly_orchestrator/supervisor.py` — MODIFY (finalize runner fallback)
**Done when:** `pytest tests/ -q` passes with zero failures; a feature dir with only `STATE.json` and `EVENTS.jsonl` (no `pathly.db`) loads correctly via the fallback paths.
**Delivers stories:** S4.2
**Depends on:** Phase 7 (migration script available for test fixture setup)
**Enables:** DONE — feature complete
**Details:**
- Add a pytest fixture in `tests/conftest.py` (or `test_db.py`) that creates a feature dir with only legacy files and asserts `read_state()` + `read_events()` return correct data without a DB present.
- Confirm `supervisor.py:recover_stale_mirrors()` does not crash on a directory with no `pathly.db`.
- Run full suite: `pytest tests/ -q`. Fix any regressions.
- After suite is green, write `pathly/plans/fsm-sqlite/VERIFY.md`:
  ```
  RESULT: PASS
  All 4 conversations complete. pytest tests/ -q green. SQLite layer active for new plans; legacy fallback confirmed for old plans.
  ```
**Verify:** `pytest tests/ -q` — zero failures

---

## Prerequisites
- Python stdlib `sqlite3` available (standard in all CPython 3.8+; verified in Phase 0)
- No external dependencies added — `db.py` uses only stdlib `sqlite3`, `json`, `threading`, `pathlib`
- Existing `pathly-setup claude --apply` workflow unchanged (db.py is a Python-internal module, not exposed as adapter skill)

## Key Decisions
- **One DB per feature folder** (not one central DB): preserves isolation between features, matches existing dir-per-feature structure, allows independent deletion/archival of completed features.
- **WAL mode + NORMAL sync**: allows concurrent readers (http_server.py SSE + status_endpoint) with one writer (FSM/supervisor); `NORMAL` is safe for this use case (OS crash could lose last transaction, but not corrupt DB).
- **No ORM**: `db.py` uses raw `sqlite3` — no new dependencies, no migration framework overhead. Schema changes are handled by adding columns with `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` in future PRs.
- **Backward compat via DB-exists check**: `if (feature_dir / "pathly.db").exists()` guard in `read_*` functions; write functions always use SQLite (new writes go to DB, not files). Old plans can be migrated on demand via the migration script.
- **Agent-written STATE.json not removed**: agents write STATE.json via the Write tool; that file stays on disk as a human-readable snapshot. The Python orchestrator layer reads SQLite as authoritative. This avoids needing an HTTP endpoint for agent state updates.
