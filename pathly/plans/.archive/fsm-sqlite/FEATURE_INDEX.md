---
name: Feature Index
---
# fsm-sqlite — Feature Index

> **Read this first.** Every agent working on this feature should load this file before any other plan file.
> It maps every file in this folder so you can fetch only what you need in one read.

---

## Plan files

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `FEATURE_INDEX.md` | Planner | All agents | This file — single entry point for feature context |
| `USER_STORIES.md` | Planner | Tester, Reviewer | Acceptance criteria — the contract |
| `IMPLEMENTATION_PLAN.md` | Planner | Builder, Architect | Phase-by-phase design — the what and how |
| `CONVERSATION_PROMPTS.md` | Planner | Builder | Exact builder prompts — one section per conversation |
| `PROGRESS.md` | Builder, Orchestrator | Orchestrator, Builder | Conversation status — the checkpoint |
| `ARCHITECTURE_PROPOSAL.md` | Planner | Builder, Architect | SQLite schema design + layer decisions |
| `EDGE_CASES.md` | Planner | Builder, Tester | Concurrency, migration, and fallback failure modes |
| `HAPPY_FLOW.md` | Planner | Builder | Golden-path narrative for a full pipeline run |
| `FLOW_DIAGRAM.md` | Planner | Builder | ASCII diagram: old file I/O vs new SQLite layer |

### Optional plan files (present if signals fired)

| File | Present? | Purpose |
|---|---|---|
| `ARCHITECTURE_PROPOSAL.md` | yes | SQLite schema + design decisions |
| `EDGE_CASES.md` | yes | Concurrency, corruption, backward compat risks |
| `HAPPY_FLOW.md` | yes | End-to-end pipeline run through SQLite layer |
| `FLOW_DIAGRAM.md` | yes | Layered ASCII diagram of new data flow |

---

## Codebase touchpoints

Files in the live repo that this feature reads or modifies.

| Codebase file | Conversation | What changes |
|---|---|---|
| `src/pathly_orchestrator/db.py` | Conv 1 | NEW — SQLite schema + connection management + all CRUD helpers |
| `tests/test_db.py` | Conv 1 | NEW — unit tests for db.py (all three tables) |
| `src/pathly_orchestrator/eventlog.py` | Conv 2 | Replace file I/O in append_event(), read_events(), write_state(), read_state() with db.py calls; add .jsonl/.json fallback for plans without DB |
| `src/pathly_orchestrator/supervisor.py` | Conv 2 + Conv 3 | Conv 2: fix direct EVENTS.jsonl writes → call append_event(); Conv 3: replace _write_mirror() + recover_stale_mirrors() → db.py runner_state |
| `src/pathly_orchestrator/http_server.py` | Conv 3 | Replace _tail_events() file-seek SSE → SQLite seq-number polling |
| `src/pathly_orchestrator/runner.py` | Conv 3 | Replace read_last_agent_done() file scan → SQLite query |
| `scripts/migrate_to_sqlite.py` | Conv 4 | NEW — one-shot import of existing STATE.json + EVENTS.jsonl + RUNNER_STATE.json into SQLite |

> **Verify these paths exist before editing.** Glob each one. If a path is wrong, correct it before proceeding.

---

## Conversation map

| Conv | Title | Stories | Status | Key files touched |
|---|---|---|---|---|
| 1 | DB Foundation | S1.1 | TODO | `db.py` (new), `test_db.py` (new) |
| 2 | Migrate event log + FSM state | S2.1, S2.2 | TODO | `eventlog.py`, `supervisor.py` (partial) |
| 3 | Migrate runner state + watcher + SSE tail | S3.1, S3.2, S3.3 | TODO | `supervisor.py`, `http_server.py`, `runner.py` |
| 4 | Migration script + backward compat | S4.1, S4.2 | TODO | `scripts/migrate_to_sqlite.py`, `eventlog.py` (fallback) |

---

## Feedback files (transient — deleted after resolution)

Live in `pathly/plans/fsm-sqlite/feedback/`. A file existing = issue open.

| File | Written by | Resolved by |
|---|---|---|
| `REVIEW_FAILURES.md` | Reviewer | Builder |
| `TEST_FAILURES.md` | Tester | Builder |
| `IMPL_QUESTIONS.md` | Builder [REQ] | Planner |
| `DESIGN_QUESTIONS.md` | Builder [ARCH] | Architect |
| `HUMAN_QUESTIONS.md` | Any agent | User |
