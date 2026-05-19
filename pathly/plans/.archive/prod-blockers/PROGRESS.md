# prod-blockers — Progress

## Status: COMPLETE

## Baseline

> Run `python -m pytest tests/ -x -q 2>&1 | tee pathly/plans/prod-blockers/baseline_failures.txt` before Conversation 1 and paste the result here.

(not yet recorded)

---

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Strip traceback from 500 responses | Conv 1 | DONE |
| S1.2 | Replace deprecated datetime.utcnow() in fsm.py | Conv 1 | DONE |
| S1.3 | Add timeout to subprocess git calls in fsm.py | Conv 1 | DONE |
| S2.1 | Manifest integrity on write and read | Conv 2 | DONE |
| S3.1 | Reject path-traversal attempts in /events/stream | Conv 3 | DONE |
| S3.2 | Stop tailer threads when last SSE client disconnects | Conv 3 | DONE |
| S4.1 | Rollback test — no orphaned files after mid-install failure | Conv 4 | DONE |
| S4.2 | Parametrized test for required manifest JSON fields | Conv 4 | DONE |

---

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1.1, 1.2, 1.3 | S1.1, S1.2, S1.3 | DONE | `python -m pytest tests/ -x -q` |
| 2 | 2.1 | S2.1 | DONE | `python -m pytest tests/ -x -q` |
| 3 | 3.1, 3.2 | S3.1, S3.2 | DONE | `python -m pytest tests/ -x -q` |
| 4 | 4.1, 4.2 | S4.1, S4.2 | DONE | `python -m pytest tests/ -x -q` |

---

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1.1 | `src/pathly_orchestrator/http_server.py` | Remove traceback from 500 handlers; add logging.exception() | No "traceback" key in 500 responses from either endpoint | DONE |
| 1 | 1.2 | `src/pathly_orchestrator/fsm.py` | Replace datetime.utcnow() with datetime.now(timezone.utc) | String "datetime.utcnow" absent from file | DONE |
| 1 | 1.3 | `src/pathly_orchestrator/fsm.py` | Add timeout=30 + TimeoutExpired handling to both git subprocess calls | Both subprocess.run() calls have timeout=30; TimeoutExpired raises RuntimeError | DONE |
| 2 | 2.1 | `src/install_cli/materialize.py` | Add _manifest_version + SHA-256 hash on write; validate on load; abort uninstall on missing files | Save writes hash+version; load raises ValueError on mismatch; uninstall aborts on missing entries | DONE |
| 3 | 3.1 | `src/pathly_orchestrator/http_server.py` | Resolve + boundary-check project_root in /events/stream | Path-traversal project_root returns 400 | DONE |
| 3 | 3.2 | `src/pathly_orchestrator/http_server.py` | Stop tailer threads when last client disconnects | _tailers entry removed and stop_evt.set() called when client list empties | DONE |
| 4 | 4.1 | `tests/test_rollback.py` | Test no orphaned files after mid-install failure | Test collected and passing | DONE |
| 4 | 4.2 | `tests/test_manifests.py` | Parametrized test for required manifest fields across 3 files | 3 parametrized cases collected and passing | DONE |

---

## Prerequisites
- Python environment with all dependencies installed.
- `git` available on PATH.
- All 3 manifest JSON files exist at paths listed in FEATURE_INDEX.md.

## Blocked By
- Nothing
