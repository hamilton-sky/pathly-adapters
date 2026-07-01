---
name: Edge Cases
---

# Comms Board (Phase 1 — Backend Core) — Edge Cases

## Category 1: sqlite-vec extension availability

### EC-1.1: Extension fails to load on the host platform
- **Trigger:** SQLite compiled without `enable_load_extension`, or the sqlite-vec wheel is missing for the platform
- **Current behavior:** N/A (feature is new)
- **Expected behavior:** `get_db()` catches the load failure, sets `_VEC_AVAILABLE = False`, logs one warning, and the server starts normally. All search paths fall back to recency (`ORDER BY ts DESC LIMIT k`).
- **Handled in:** Phase 2 (connection flag) + Phase 4 (query branch)

### EC-1.2: vec0 virtual table creation attempted without the extension
- **Trigger:** migration runs while `_VEC_AVAILABLE` is false
- **Expected behavior:** the `CREATE VIRTUAL TABLE comms_embeddings USING vec0(...)` is skipped; `comms_messages` is still created so message storage and recency search work.
- **Handled in:** Phase 3

## Category 2: Embedding timing

### EC-2.1: Message posted before the model is warm
- **Trigger:** a `/comms/post` arrives during the first ~1–2s of server life
- **Expected behavior:** the message is stored and returned immediately; embedding is queued on the daemon thread and lands once the model finishes loading. Exact-match `GET /comms` works in the meantime.
- **Handled in:** Phase 5 (async) + Phase 7 (startup warm thread)

### EC-2.2: Empty or whitespace-only text
- **Trigger:** `text` is `""` or only spaces
- **Expected behavior:** `embed()` is skipped; the message is still stored (it may carry options/artifact fields). No embedding row is written; recency search still surfaces it.
- **Handled in:** Phase 5

## Category 3: State and configuration

### EC-3.1: board_scope written into STATE.json gets dropped
- **Trigger:** a naive implementation stores board_scope in STATE.json; the next `write_state()` does a full `INSERT OR REPLACE` of state_json and silently drops the key
- **Expected behavior:** board_scope is stored in `app_settings` under `board_scope:{project_root}:{feature}`, never in STATE.json — so `write_state()` cannot clobber it.
- **Handled in:** Phase 10 (CONSULTATION §1.2 Risk 2)

### EC-3.2: board_scope absent for a feature
- **Trigger:** a feature that predates this plan calls `/next_action`
- **Expected behavior:** `get_board_scope` returns `{feature:true, project:true, global:true}` — fully backward compatible; existing features get full board context by default.
- **Handled in:** Phase 10

### EC-3.3: All three scopes disabled
- **Trigger:** board_scope = `{feature:false, project:false, global:false}`
- **Expected behavior:** `retrieve_board_context()` returns `""`; no block is appended; the prompt is identical to today's. No error.
- **Handled in:** Phase 9 + Phase 10

## Category 4: Retrieval scale and prompt size

### EC-4.1: Very large global board
- **Trigger:** the global board accumulates thousands of messages over months
- **Expected behavior:** queries filter `status NOT IN ('trashed','archived')` and cap the search space (`LIMIT 2000`) before vector comparison, keeping `/next_action` latency bounded.
- **Handled in:** Phase 4 query design (SPEC §6.3 / CONSULTATION §1.2 Risk 5)

### EC-4.2: Many pending decisions inflate the prompt
- **Trigger:** dozens of `decision` messages all marked pending
- **Expected behavior:** mandatory decisions are always included, but the retrieved-by-similarity set stays bounded (feature 3 + project 2 + global 1). If decisions grow unbounded, the block lists them compactly (one line each). Bounded prompt growth is an explicit acceptance criterion (S2.1).
- **Handled in:** Phase 9

## Category 5: Concurrency

### EC-5.1: Concurrent posts on the shared connection
- **Trigger:** two `/comms/post` calls race
- **Expected behavior:** all writes go through the existing `_get_write_lock(conn)` serialization; no `database is locked` errors under WAL + busy_timeout.
- **Handled in:** Phase 4 (reuse the established write-lock pattern)

## Known Limitations
- **No Studio UI** — Phase 1 is backend only; posting/reading is via curl. The CommsPanel is the `comms-board-studio` plan.
- **`/comms/attach` is a stub** — artifact ingestion (PDF/URL/code chunking) is SPEC Phase 4, a later plan folder.
- **Agents are not yet wired to post** — skill integration (build.md/review.md reading and posting) is the `comms-board-skills` plan.
- **No cross-feature promote/trash UI** — promote-before-delete and the 30-day purge job are later phases; `purge_expired_trash` exists as a helper but is not scheduled in Phase 1.
