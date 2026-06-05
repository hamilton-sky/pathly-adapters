# TEST_FAILURES — fsm-server-sqlite

**Run:** `python -m pytest tests/ -q --tb=short`
**Result:** 2 failed, 428 passed, 3 skipped
**Date:** 2026-06-05

---

## Failing Stories

### Story 2 — `record_phase` endpoint writes to SQLite

**AC2 (PASS — by implication):** EVENTS.jsonl is not written when pathly.db exists.
**AC3 (FAIL — partially):** The legacy fallback behavior is broken for the test setup.

Two tests in `tests/test_observability.py` FAIL because they assert that
`EVENTS.jsonl` is written after a `POST /record_phase` call, but the
implementation now always writes to SQLite (via `eventlog.append_event` →
`db.get_db()` → `db.append_event()`), even when no pre-existing `pathly.db`
was present. The JSONL fallback path no longer exists in `eventlog.append_event`.

#### test_record_phase_start_valid

```
tests/test_observability.py:46: AssertionError
  assert events_path.exists()
  where events_path = WindowsPath('.../pathly/plans/my-feature/EVENTS.jsonl')
```

**Expected:** After `POST /record_phase`, `EVENTS.jsonl` exists in the feature dir (legacy fallback).
**Actual:** `EVENTS.jsonl` was NOT created. The event was written to `pathly.db` instead.
**File:** `tests/test_observability.py:30`

#### test_record_phase_done_all_optional_fields

```
tests/test_observability.py:79: FileNotFoundError
  'C:\\tmp\\pathly-tests\\...\\pathly\\plans\\my-feature\\EVENTS.jsonl'
```

**Expected:** After `POST /record_phase`, the event payload is readable from `EVENTS.jsonl`.
**Actual:** `EVENTS.jsonl` does not exist — event written to SQLite only.
**File:** `tests/test_observability.py:60`

#### Root cause

`eventlog.append_event` (eventlog.py:61) always calls `_db.get_db(feature_dir)` and
writes to SQLite regardless of whether a `pathly.db` already existed. The "legacy
fallback to EVENTS.jsonl when pathly.db does NOT exist" path described in Story 2 AC3
is not implemented. The tests in `test_observability.py` were written against the old
direct-JSONL behavior and have not been updated to read from SQLite.

The fix can go in one of two directions (builder decides):
1. Update `test_observability.py::test_record_phase_start_valid` and
   `test_observability.py::test_record_phase_done_all_optional_fields` to read
   events from SQLite via `db.read_events` (matching how `test_http_server.py`
   was updated for `record_activity` tests — Story 7 pattern).
2. Restore a JSONL fallback in `eventlog.append_event` when no `pathly.db` exists
   (to satisfy Story 2 AC3 literally). This would be a larger scope change.

Option 1 is consistent with the direction taken for Story 7 and Story 8.

---

## Story 8 — AC1 FAIL

**AC1:** `python -m pytest tests/ -q` exits with code 0.
**Actual:** Exit code 1. 2 tests fail (see above).

---

## Full Test Plan

### Story 1 — `_append_agent_done_event` writes to SQLite

```
Story 1: _append_agent_done_event writes to SQLite
  Criterion: AC1 — POST /record_activity event readable via db.read_events
  Test: test_record_activity_appends_complete_agent_done_event (test_http_server.py:171)
  Status: PASS

  Criterion: AC2 — no EVENTS.jsonl written when pathly.db exists
  Test: test_record_activity_appends_complete_agent_done_event — no JSONL assertion
  Status: PASS

  Criterion: AC3 — falls back to EVENTS.jsonl when no pathly.db
  Test: test_record_activity_uses_total_tokens_when_split_is_missing (test_http_server.py:212)
  Status: PASS
  Notes: Legacy path is exercised in existing tests; both pass.

  Criterion: AC4 — event payload shape unchanged
  Test: test_record_activity_appends_complete_agent_done_event asserts all required fields
  Status: PASS
```

### Story 2 — `record_phase` endpoint writes to SQLite

```
Story 2: record_phase endpoint writes to SQLite
  Criterion: AC1 — POST /record_phase event readable via db.read_events
  Test: No test reads from db.read_events after /record_phase
  Status: NOT COVERED
  Notes: test_record_phase_start_valid reads EVENTS.jsonl, not SQLite.

  Criterion: AC2 — no EVENTS.jsonl written when pathly.db exists
  Test: No explicit test for this path
  Status: NOT COVERED

  Criterion: AC3 — falls back to EVENTS.jsonl when no pathly.db
  Test: test_record_phase_start_valid / test_record_phase_done_all_optional_fields
  Status: FAIL
  Notes: Both tests assert EVENTS.jsonl is written, but implementation writes to SQLite.
         Tests fail with FileNotFoundError / AssertionError on EVENTS.jsonl path.

  Criterion: AC4 — existing 400 validation unchanged
  Test: test_record_phase_missing_required_field (x4), test_record_phase_invalid_event_type,
        test_record_phase_invalid_phase
  Status: PASS
```

### Story 3 — `_stage_brief` reads recent events from SQLite

```
Story 3: _stage_brief reads recent events from SQLite
  Criterion: AC1 — reads last 3 events from db.read_events when pathly.db exists
  Test: No dedicated test for SQLite path in _stage_brief
  Status: NOT COVERED
  Notes: Integration is tested indirectly via next_action tests, but no test isolates
         the SQLite branch of _stage_brief.

  Criterion: AC2 — EVENTS.jsonl fallback when no pathly.db
  Test: Not explicitly tested
  Status: NOT COVERED

  Criterion: AC3 — recent_events field shape unchanged
  Test: test_fsm_ops.py next_action tests check stage_brief presence
  Status: PASS
```

### Story 4 — `on_state_counter` reads STATE from eventlog

```
Story 4: on_state_counter reads STATE from eventlog
  Criterion: AC1 — reads from DB when no STATE.json
  Test: test_on_state_counter_reads_from_db (test_fsm.py:465)
  Status: PASS

  Criterion: AC2 — STATE.json-only (legacy) unchanged
  Test: Existing FSM tests cover legacy path; test_fsm.py full suite PASS
  Status: PASS

  Criterion: AC3 — python -m pytest tests/test_fsm.py -q passes
  Test: 35 passed, 0 failed
  Status: PASS
```

### Story 5 — `update_progress` reads/writes STATE through eventlog

```
Story 5: update_progress reads/writes STATE through eventlog
  Criterion: AC1 — db.read_state shows incremented convs_done after update_progress
  Test: test_update_progress_conv_done_increments_db (test_fsm.py:490)
  Status: PASS

  Criterion: AC2 — STATE.json still written as snapshot
  Test: Implicit in test_update_progress_conv_done_increments_db
  Status: PASS

  Criterion: AC3 — legacy STATE.json-only path unchanged
  Test: Existing FSM tests; all 35 pass
  Status: PASS

  Criterion: AC4 — python -m pytest tests/test_fsm.py -q passes
  Test: 35 passed, 0 failed
  Status: PASS
```

### Story 6 — `build_pipeline_history_block` reads events from SQLite

```
Story 6: build_pipeline_history_block reads events from SQLite
  Criterion: AC1 — returns non-empty block from DB when pathly.db exists
  Test: test_pipeline_history_block_format (test_runner.py:263) — uses file path, not dir
  Status: NOT COVERED
  Notes: No test passes a directory path with pathly.db to trigger the SQLite branch.

  Criterion: AC2 — reads EVENTS.jsonl when no pathly.db (legacy)
  Test: test_pipeline_history_block_format — writes to EVENTS.jsonl, passes file path
  Status: PASS

  Criterion: AC3 — returned string format unchanged
  Test: test_pipeline_history_block_format checks block structure
  Status: PASS
```

### Story 7 — Existing tests updated for SQLite-primary writes

```
Story 7: Existing tests updated for SQLite-primary writes
  Criterion: AC1 — test_record_activity_appends_complete_agent_done_event reads from SQLite
  Test: test_record_activity_appends_complete_agent_done_event (test_http_server.py:171)
  Status: PASS

  Criterion: AC2 — no other test_http_server.py test fails due to migration
  Test: python -m pytest tests/test_http_server.py -> 22 passed
  Status: PASS

  Criterion: AC3 — python -m pytest tests/ -q shows zero failures/errors
  Test: Full suite result: 2 failed (in test_observability.py)
  Status: FAIL
  Notes: test_observability.py tests were NOT updated to read from SQLite.
```

### Story 8 — Full test suite green after migration

```
Story 8: Full test suite green after migration
  Criterion: AC1 — python -m pytest tests/ -q exits code 0
  Test: Exit code 1; 2 failures in test_observability.py
  Status: FAIL

  Criterion: AC2 — no test file imports removed EVENTS.jsonl path logic
  Test: test_observability.py:46,79 still assert EVENTS.jsonl exists
  Status: FAIL

  Criterion: AC3 — at least one test per changed function covers new SQLite path
  Test: record_activity: COVERED. record_phase SQLite path: NOT COVERED.
  Status: FAIL
```

---

## Summary

| Story | Status | Notes |
|---|---|---|
| 1 | PASS | All ACs pass |
| 2 | FAIL | AC3 FAIL; AC1/AC2 NOT COVERED |
| 3 | NOT COVERED | No dedicated SQLite branch test |
| 4 | PASS | DB test present and passing |
| 5 | PASS | DB test present and passing |
| 6 | PARTIAL | AC1 NOT COVERED (SQLite dir branch) |
| 7 | FAIL | test_observability.py not updated |
| 8 | FAIL | 2 failures, exit code 1 |

**Failures to fix:**
1. `tests/test_observability.py::test_record_phase_start_valid` — update to read from SQLite
2. `tests/test_observability.py::test_record_phase_done_all_optional_fields` — update to read from SQLite
