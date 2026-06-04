# 03 — Artifact Map: fsm-sqlite

Every file produced or consumed during this pipeline run.

---

## Plan files (FSM persistent state)

These files are the pipeline's memory. An interrupted run can be resumed by reading
PROGRESS.md and re-entering at the last incomplete conversation.

| File | Written by | Read by | Purpose |
|---|---|---|---|
| USER_STORIES.md | Planner | Tester | Acceptance criteria — the contract |
| IMPLEMENTATION_PLAN.md | Planner | Planner | Exact code changes — the design |
| CONVERSATION_PROMPTS.md | Planner | Builder agents | Verbatim prompts — the instructions |
| PROGRESS.md | Orchestrator | Orchestrator | Conversation status — the checkpoint |
| RETRO.md | Retro agent | Humans, /lessons | What we learned — the feedback loop |

---

## Transient feedback files (deleted after resolution)

These files no longer exist. They were the inter-agent communication medium.

| File | Written by | Resolved by | Content summary |
|---|---|---|---|
| REVIEW_FAILURES.md (conv 1) | Reviewer | Builder (conv 2) | BEGIN IMMEDIATE in mark_stale_runners conflicts with sqlite3 implicit tx management |
| REVIEW_FAILURES.md (conv 4) | Reviewer | Builder (conv 4) | Migration script non-idempotent; PROGRESS.md S2.1–S3.3 marked TODO incorrectly |
| TEST_FAILURES.md | Tester | Builder | S3.1 dual-write not removed; S3.3 Last-Event-ID not implemented |

---

## Source files changed

| File | Stories | What changed |
|---|---|---|
| `src/pathly_orchestrator/db.py` (NEW) | S1.1, S1.2, S1.3, S1.4 | SQLite schema (events, state, runner_state tables); WAL mode; CRUD helpers; per-connection write lock |
| `src/pathly_orchestrator/eventlog.py` | S2.1, S2.2 | append_event / write_state / read_events / read_state delegate to db.py; .jsonl fallbacks for legacy dirs |
| `src/pathly_orchestrator/supervisor.py` | S3.1, S3.2 | _write_mirror SQLite-only (no write_text); recover_stale_mirrors reads from SQLite with .json fallback |
| `src/pathly_orchestrator/http_server.py` | S3.3 | _tail_events polls SQLite seq-numbers; Last-Event-ID catch-up in events_stream generate() |
| `scripts/migrate_to_sqlite.py` (NEW) | S4.1 | One-shot migration CLI; idempotent (skip if events already in DB); --dry-run flag |
| `tests/test_db.py` (NEW) | S1.1–S1.4 | 14 tests: schema, CRUD, concurrent writes, backward-compat (legacy .jsonl/.json read) |
| `tests/test_http_server.py` | S3.3 | SSE Last-Event-ID reconnect test; Pyright cleanup (removed unused import) |
| `tests/test_supervisor.py` | S3.1, S3.2 | Updated 3 test assertions (file existence → db.read_runner_state); Pyright unused-param fixes |

---

## Artifact flow diagram

```
USER_STORIES.md          ←── what to build
       │
       ▼
IMPLEMENTATION_PLAN.md   ←── how to build it
       │
       ▼
CONVERSATION_PROMPTS.md  ←── exact builder prompts
       │
       ▼
PROGRESS.md              ←── which conversations done
       │
       ▼
RETRO.md                 ←── what we learned
       │
       ▼
lessons/LESSONS.md       ←── promoted patterns → next planner
pipeline-walkthrough/fsm-sqlite/  ←── metrics record → this folder
```
