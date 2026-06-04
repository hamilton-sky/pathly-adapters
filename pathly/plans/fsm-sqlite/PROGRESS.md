---
name: Progress
---
# fsm-sqlite — Progress

## Status: IN PROGRESS (Conv 1 complete)

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | SQLite DB layer | Conv 1 | DONE |
| S2.1 | EVENTS.jsonl → SQLite (event log) | Conv 2 | TODO |
| S2.2 | STATE.json → SQLite (FSM state) | Conv 2 | TODO |
| S3.1 | RUNNER_STATE.json → SQLite (runner state) | Conv 3 | TODO |
| S3.2 | AGENT_DONE watcher → SQLite seq poll | Conv 3 | TODO |
| S3.3 | SSE tail → SQLite seq-number polling | Conv 3 | TODO |
| S4.1 | Migration script for existing plans | Conv 4 | TODO |
| S4.2 | Backward compat fallback + full test suite | Conv 4 | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 0, 1, 2 | S1.1 | DONE | `pytest tests/test_db.py -v` |
| 2 | 3, 4 | S2.1, S2.2 | TODO | `pytest tests/test_orchestrator.py tests/test_fsm.py tests/test_supervisor.py tests/test_storage.py -q` |
| 3 | 5, 5b, 6 | S3.1, S3.2, S3.3 | TODO | `pytest tests/test_supervisor.py tests/test_http_server.py tests/test_runner.py tests/test_runner_endpoints.py -q` |
| 4 | 7, 8 | S4.1, S4.2 | TODO | `pytest tests/ -q` |

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 0 Pre-flight | `tests/` | Run baseline tests + verify sqlite3 | `PREFLIGHT.md` written | DONE |
| 1 | 1 Create db.py | `src/pathly_orchestrator/db.py` | New SQLite layer — schema + all CRUD | Import succeeds, no errors | DONE |
| 1 | 2 Create test_db.py | `tests/test_db.py` | Unit tests for all db.py helpers | `pytest tests/test_db.py -v` green | DONE |
| 2 | 3 Migrate eventlog.py | `src/pathly_orchestrator/eventlog.py` | events + state reads/writes → SQLite | `pytest tests/test_fsm.py tests/test_orchestrator.py -q` green | TODO |
| 2 | 4 Fix supervisor direct writes | `src/pathly_orchestrator/supervisor.py` | Remove direct .jsonl writes | grep for `.jsonl` returns 0; supervisor tests green | TODO |
| 3 | 5 Migrate runner state | `src/pathly_orchestrator/supervisor.py` | _write_mirror() + recover_stale_mirrors() → SQLite | grep for `RUNNER_STATE.json` write returns 0; supervisor tests green | TODO |
| 3 | 5b Replace agent_done watcher | `src/pathly_orchestrator/supervisor.py` | _agent_done_watcher() → SQLite seq poll (150ms) | grep for EVENTS.jsonl returns 0; supervisor tests green | TODO |
| 3 | 6 Migrate SSE + runner.py | `src/pathly_orchestrator/http_server.py`, `src/pathly_orchestrator/runner.py` | _tail_events() + read_last_agent_done() → SQLite | http_server + runner tests green | TODO |
| 4 | 7 Migration script | `scripts/migrate_to_sqlite.py` | Import existing .json/.jsonl into SQLite | dry-run exits 0; real run populates DB | TODO |
| 4 | 8 Backward compat + full suite | `src/pathly_orchestrator/eventlog.py`, `src/pathly_orchestrator/supervisor.py` | Finalize fallback paths; full test suite | `pytest tests/ -q` zero failures | TODO |

## Prerequisites
- Python stdlib sqlite3 available (verified in Phase 0)
- No new package dependencies

## Blocked By
- Nothing
