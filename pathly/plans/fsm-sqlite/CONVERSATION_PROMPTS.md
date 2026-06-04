---
name: Conversation Guide
---
# fsm-sqlite — Conversation Guide

Split into 4 conversations. Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: DB Foundation (Phases 0–2)

**Stories delivered:** S1.1

**Prompt to paste:**
```
Read pathly/plans/fsm-sqlite/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-sqlite Conversation 1 (Phases 0–2) from pathly/plans/fsm-sqlite/IMPLEMENTATION_PLAN.md.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/db.py` — CREATE (new file)
- `tests/test_db.py` — CREATE (new file)
- `pathly/plans/fsm-sqlite/PREFLIGHT.md` — CREATE (baseline capture)

Scope:

**Phase 0 — Pre-flight:**
- Run `pytest tests/ -q --tb=no` and record which tests already fail (baseline).
- Run `python -c "import sqlite3; print(sqlite3.sqlite_version)"` to confirm stdlib availability.
- Write both outputs to `pathly/plans/fsm-sqlite/PREFLIGHT.md`.

**Phase 1 — Create src/pathly_orchestrator/db.py:**
See IMPLEMENTATION_PLAN.md Phase 1 for the full spec. Key points:
- Module-level `_conn_cache: dict[str, sqlite3.Connection]` + `_cache_lock: threading.Lock`
- `get_db(feature_dir: Path) -> sqlite3.Connection` — WAL + NORMAL sync, cached per path
- `_init_schema(conn)` — three CREATE TABLE IF NOT EXISTS statements + index
- Export all helpers: `append_event`, `read_events`, `read_last_agent_done`, `write_state`, `read_state`, `write_runner_state`, `read_runner_state`, `mark_stale_runners`
- No external dependencies — stdlib sqlite3, json, threading, pathlib only

Table schemas (copy exactly):
```sql
-- fsm_events
CREATE TABLE IF NOT EXISTS fsm_events (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    feature      TEXT    NOT NULL,
    type         TEXT    NOT NULL,
    ts           TEXT    NOT NULL,
    schema_version INTEGER DEFAULT 1,
    payload      TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_feature ON fsm_events(feature, seq);

-- fsm_state
CREATE TABLE IF NOT EXISTS fsm_state (
    feature             TEXT PRIMARY KEY,
    current             TEXT NOT NULL,
    rigor               TEXT,
    current_conversation INTEGER,
    retry_count_by_key  TEXT,
    iteration_by_stage  TEXT,
    updated_at          TEXT NOT NULL,
    conv_start_sha      TEXT,
    convs_total         INTEGER,
    convs_done          INTEGER,
    build_baseline      TEXT,
    extra               TEXT
);

-- runner_state
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
    autonomy        TEXT    DEFAULT '{}',
    pending_menu    TEXT,
    error_kind      TEXT,
    open_session    TEXT,
    updated_at      TEXT
);
```

**Phase 2 — Create tests/test_db.py:**
Write tests using `tmp_path` pytest fixture. Required tests (see IMPLEMENTATION_PLAN.md Phase 2):
- test_get_db_creates_tables
- test_get_db_cached
- test_append_and_read_events
- test_read_events_since_seq
- test_read_last_agent_done
- test_write_and_read_state
- test_read_state_missing
- test_write_and_read_runner_state
- test_mark_stale_runners
- test_concurrent_appends (two threads, 50 events each, assert 100 rows no gaps)

Architectural rules:
- db.py must import ONLY from stdlib (sqlite3, json, threading, pathlib). No pathly_orchestrator imports.
- Do not modify any existing source file in this conversation.
- Do NOT touch eventlog.py, supervisor.py, http_server.py, runner.py yet.

Verify: `pytest tests/test_db.py -v` — all tests green.
After verification passes, write `pathly/plans/fsm-sqlite/VERIFY.md` — wait, do NOT write VERIFY.md yet (that comes after Conv 4). Instead update PROGRESS.md: set Conv 1 phases 0, 1, 2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** `src/pathly_orchestrator/db.py` exists and all 10 tests in `tests/test_db.py` pass.
**Files touched:** `src/pathly_orchestrator/db.py` (new), `tests/test_db.py` (new), `pathly/plans/fsm-sqlite/PREFLIGHT.md` (new)

---

## Conversation 2: Migrate event log + FSM state (Phases 3–4)

**Stories delivered:** S2.1, S2.2

**Prompt to paste:**
```
Read pathly/plans/fsm-sqlite/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-sqlite Conversation 2 (Phases 3–4) from pathly/plans/fsm-sqlite/IMPLEMENTATION_PLAN.md.
Conversation 1 is complete: src/pathly_orchestrator/db.py exists and tests/test_db.py passes.

**Before editing anything:** read src/pathly_orchestrator/eventlog.py and src/pathly_orchestrator/supervisor.py
in full to understand the current file I/O patterns before changing them.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/eventlog.py` — MODIFY (events + state reads/writes → SQLite)
- `src/pathly_orchestrator/supervisor.py` — MODIFY (remove direct .jsonl writes)

Scope:

**Phase 3 — Migrate eventlog.py:**
- `append_event()`: remove _APPEND_LOCK, fcntl import, direct file write → call db.append_event()
- `read_events()`: if pathly.db exists → db.read_events(); else fall back to .jsonl as-is
- `write_state()`: remove .tmp + fsync + rename → call db.write_state()
- `read_state()`: if pathly.db exists → db.read_state(); else fall back to STATE.json as-is
- Get db connection via: `conn = db.get_db(_resolve_path(feature))` (reuse existing path resolver)
- Import db: `from pathly_orchestrator import db` at top of eventlog.py
- Do not change any validation logic (transition rules, schema_version injection, ts auto-fill) — only persistence calls change

**Phase 4 — Fix supervisor.py direct .jsonl writes:**
- Read supervisor.py; find every location that opens or writes EVENTS.jsonl directly
- Replace each with: `eventlog.append_event(feature, event_dict)`
- Ensure eventlog is imported in supervisor.py
- Do not change any business logic — only the storage call

Architectural rules:
- eventlog.py public API (function signatures) must not change — callers must continue to work unchanged
- _APPEND_LOCK and fcntl removal is only safe because db.py uses BEGIN IMMEDIATE for serialization — confirm this in db.py before removing the lock
- Do NOT touch http_server.py, runner.py, or supervisor.py RUNNER_STATE logic yet

Verify:
- `grep -n "EVENTS.jsonl\|\.jsonl" src/pathly_orchestrator/supervisor.py` returns 0 matches
- `pytest tests/test_orchestrator.py tests/test_fsm.py tests/test_supervisor.py tests/test_storage.py -q` passes

After verification passes, update pathly/plans/fsm-sqlite/PROGRESS.md: Conv 2 phases 3, 4 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** eventlog.py uses SQLite for all reads/writes; supervisor.py has no direct .jsonl writes; test suite green.
**Files touched:** `src/pathly_orchestrator/eventlog.py`, `src/pathly_orchestrator/supervisor.py`

---

## Conversation 3: Migrate runner state + watcher + SSE tail (Phases 5, 5b, 6)

**Stories delivered:** S3.1, S3.2, S3.3

**Prompt to paste:**
```
Read pathly/plans/fsm-sqlite/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-sqlite Conversation 3 (Phases 5, 5b, 6) from pathly/plans/fsm-sqlite/IMPLEMENTATION_PLAN.md.
Conversations 1 and 2 are complete: db.py exists, eventlog.py uses SQLite, supervisor.py has no direct .jsonl writes.

**Before editing anything:** read src/pathly_orchestrator/supervisor.py, src/pathly_orchestrator/http_server.py,
and src/pathly_orchestrator/runner.py in full to understand current RUNNER_STATE, watcher, and SSE patterns.

**Codebase files this conversation touches:**
- `src/pathly_orchestrator/supervisor.py` — MODIFY (_write_mirror + recover_stale_mirrors + _agent_done_watcher → SQLite)
- `src/pathly_orchestrator/http_server.py` — MODIFY (_tail_events → seq-number polling)
- `src/pathly_orchestrator/runner.py` — MODIFY (read_last_agent_done → SQLite query)

Scope:

**Phase 5 — Migrate supervisor.py RUNNER_STATE:**
- `_write_mirror(runner_dict)` → call `db.write_runner_state(conn, feature, runner_dict)`; remove write_text() call
- `recover_stale_mirrors()` → for each `pathly/plans/*/pathly.db` found: call `db.mark_stale_runners(conn)`; if no DB found for a feature dir, fall back to reading RUNNER_STATE.json and rewriting it as before
- Get feature_dir from runner_dict['project_root'] or supervisor's existing path resolution

**Phase 5b — Replace _agent_done_watcher() with SQLite poll:**
- Before spawning the PTY for a stage, capture last_seq:
  `last_seq = conn.execute("SELECT MAX(seq) FROM fsm_events WHERE feature=?", (feature,)).fetchone()[0] or 0`
- Replace the file-tail loop in _agent_done_watcher() (or equivalent) with a SQLite poll:
  - Every 150ms: `rows = db.read_events(conn, feature, since_seq=last_seq)`
  - For each row: if `row["type"] == "AGENT_DONE"` → return the event dict
  - Update `last_seq` as rows are consumed
  - After `timeout` seconds with no AGENT_DONE: raise TimeoutError (same behavior as before)
- Filter by feature column — two concurrent runs for different features must not cross-signal
- Remove any file-open/read calls for EVENTS.jsonl in this function

**Phase 6 — Migrate http_server.py _tail_events() + runner.py:**

http_server.py _tail_events():
- Replace file-open + seek loop with:
  - `last_seq = int(request.headers.get("Last-Event-ID", 0))` for reconnect support
  - Poll loop: `events = db.read_events(conn, feature, since_seq=last_seq)`; for each: yield SSE with `id: {seq}\ndata: {payload}\n\n`; update last_seq; sleep
- Do not change SSE response headers or the outer generator structure

runner.py read_last_agent_done():
- Replace line-scan with: `return db.read_last_agent_done(conn, feature)`

Architectural rules:
- SSE stream must remain a generator — do not change the response type or content-type header
- Do NOT add any new HTTP endpoints
- Do NOT touch eventlog.py in this conversation

Verify:
- `grep -n "EVENTS.jsonl\|RUNNER_STATE.json" src/pathly_orchestrator/supervisor.py` returns 0 write calls
- `pytest tests/test_supervisor.py tests/test_http_server.py tests/test_runner.py tests/test_runner_endpoints.py -q` passes

After verification passes, update pathly/plans/fsm-sqlite/PROGRESS.md: Conv 3 phases 5, 6 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** RUNNER_STATE.json no longer written; SSE tail uses SQLite; runner.py query uses SQLite.
**Files touched:** `src/pathly_orchestrator/supervisor.py`, `src/pathly_orchestrator/http_server.py`, `src/pathly_orchestrator/runner.py`

---

## Conversation 4: Migration script + backward compat (Phases 7–8)

**Stories delivered:** S4.1, S4.2

**Prompt to paste:**
```
Read pathly/plans/fsm-sqlite/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement fsm-sqlite Conversation 4 (Phases 7–8) from pathly/plans/fsm-sqlite/IMPLEMENTATION_PLAN.md.
Conversations 1–3 are complete: db.py, eventlog.py, supervisor.py, http_server.py, runner.py all use SQLite.

**Before editing anything:** check if scripts/ directory exists; if not, create it. Read
src/pathly_orchestrator/eventlog.py and supervisor.py to confirm fallback paths are wired correctly.

**Codebase files this conversation touches:**
- `scripts/migrate_to_sqlite.py` — CREATE
- `src/pathly_orchestrator/eventlog.py` — MODIFY (finalize any missing fallback logic)
- `src/pathly_orchestrator/supervisor.py` — MODIFY (finalize recover_stale_mirrors fallback)

Scope:

**Phase 7 — Create scripts/migrate_to_sqlite.py:**
CLI: `python scripts/migrate_to_sqlite.py [--plans-dir PATH] [--dry-run]`
- Default plans-dir: `pathly/plans`
- For each subdirectory of plans-dir (skip `.archive`):
  - If EVENTS.jsonl exists: parse line-by-line; for each valid JSON line call db.append_event() wrapped in INSERT OR IGNORE (add UNIQUE constraint: use (feature, ts, type) or a hash of payload)
  - If STATE.json exists and no fsm_state row yet: call db.write_state()
  - If RUNNER_STATE.json exists and no runner_state row yet: call db.write_runner_state()
  - Print summary: `[feature]: events=N state=ok|missing runner=ok|missing`
- --dry-run: print what would be imported, write nothing
- Malformed JSONL lines: print warning, skip, continue (no crash)
- Does NOT delete original files

**Phase 8 — Backward compat + full test suite:**
- Add a pytest fixture (in tests/test_db.py or conftest.py) that creates a feature dir with only legacy files (no pathly.db) and asserts:
  - `eventlog.read_state(feature)` returns correct data from STATE.json
  - `eventlog.read_events(feature)` returns correct data from EVENTS.jsonl
  - `supervisor.recover_stale_mirrors()` does not crash when no pathly.db exists
- Run full test suite: `pytest tests/ -q`
- Fix any regressions found

After full suite is green, write `pathly/plans/fsm-sqlite/VERIFY.md`:
```
RESULT: PASS
All 4 conversations complete. pytest tests/ -q green. SQLite layer active for new plans;
legacy fallback confirmed for old plans. Migration script tested on pathly/plans/ tree.
```
Update pathly/plans/fsm-sqlite/PROGRESS.md: Conv 4 phases 7, 8 to DONE; Status: DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Migration script works on existing plans; full test suite green; VERIFY.md written.
**Files touched:** `scripts/migrate_to_sqlite.py` (new), `src/pathly_orchestrator/eventlog.py`, `src/pathly_orchestrator/supervisor.py`, `pathly/plans/fsm-sqlite/VERIFY.md`
