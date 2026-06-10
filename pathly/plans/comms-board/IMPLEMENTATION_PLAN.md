---
name: Implementation Plan
---
# Comms Board (Phase 1 — Backend Core) — Implementation Plan

## Overview

Build the backend of the communication board: a sqlite-vec message store at three scopes,
an embedding worker, HTTP endpoints, SSE broadcast, and FSM prompt injection. The result —
a human posts a message to the board and the next agent reads it automatically in its
`## Communication Board` prompt block. No Studio changes; fully testable via curl.

## Layer Architecture

```
Plans (this file)            →  Orchestrator modules               →  Contracts / API
        ↓                               ↓                                     ↓
comms-board Phase 1          db/ + runner/ + http_server/          /comms/* + agent_hint
                                                                     ## Communication Board
```

```
db/migrations.py     comms_messages + comms_embeddings (vec0)        ← storage
db/queries/comms.py  post / get / search / acknowledge / trash       ← data access
runner/embeddings.py embed() + async worker + warm-up                ← semantics
http_server/         blueprints/comms.py + sse.py + streams.py       ← API + realtime
runner/comms_context retrieve_board_context() → markdown block       ← retrieval
fsm_ops.py           append block to agent_hint.instructions         ← injection
```

## Phases

### Phase 1: Dependencies   ← Conversation: 1
**File:** `pyproject.toml` — MODIFY: add `sqlite-vec==0.1.6` and `sentence-transformers>=2.7.0` to `[project].dependencies`
**Done when:** `pip install -e .` succeeds and `python -c "import sqlite_vec, sentence_transformers"` runs clean.
**Delivers stories:** S1.1, S1.2
**Depends on:** nothing
**Enables:** Phases 2–5
**Details:** Pin sqlite-vec exactly (`==0.1.6`) — the `FLOAT[384]` vec0 syntax is version-specific (CONSULTATION §1.2 Risk 4). sentence-transformers may use `>=`.
**Verify:** `python -c "import sqlite_vec, sentence_transformers; print('ok')"`

### Phase 2: Load sqlite-vec at connection time   ← Conversation: 1
**File:** `src/pathly_orchestrator/db/connection.py` — MODIFY: load the extension inside `get_db()` before `_run_migrations(conn)`
**Done when:** `get_db()` returns a connection on which `SELECT vec_version()` succeeds, and a missing extension degrades gracefully.
**Delivers stories:** S1.1
**Depends on:** Phase 1
**Enables:** Phase 3 (vec0 virtual table needs the extension loaded first)
**Details:** Sequence inside the `with _cache_lock` block, right after `PRAGMA` lines and **before** `_run_migrations(conn)`:
```python
try:
    conn.enable_load_extension(True)
    import sqlite_vec; sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    _VEC_AVAILABLE = True
except Exception:
    _VEC_AVAILABLE = False
    logging.warning("sqlite-vec unavailable — comms board uses recency-only retrieval")
```
Expose `_VEC_AVAILABLE` (module-level) so query helpers can branch. Critical ordering: extension load MUST precede migrations (CONSULTATION §1.2 Risk 1).
**Verify:** `python -c "from pathly_orchestrator.db.connection import get_db; print(get_db().execute('select vec_version()').fetchone())"`

### Phase 3: Comms tables migration   ← Conversation: 1
**File:** `src/pathly_orchestrator/db/migrations.py` — MODIFY: append `comms_messages` table + `comms_embeddings` vec0 virtual table
**Done when:** a fresh `get_db()` creates both tables; `SELECT` against each succeeds.
**Delivers stories:** S1.1
**Depends on:** Phase 2
**Enables:** Phase 4
**Details:** Use the exact schema in SPEC §21.1 (all lifecycle/artifact/task columns). Guard the vec0 `CREATE VIRTUAL TABLE` with `IF NOT EXISTS`; if `_VEC_AVAILABLE` is false, skip the virtual table creation (a plain fallback table is not needed — recency queries hit `comms_messages` directly). Bump the migration version counter if the file uses one.
**Verify:** `python -m pytest tests/ -q -k "migrat or comms"`

### Phase 4: Comms query helpers   ← Conversation: 1
**File:** `src/pathly_orchestrator/db/queries/comms.py` — CREATE; also MODIFY `db/queries/__init__.py` to re-export
**Done when:** posting a message then searching for it by text returns the row.
**Delivers stories:** S1.1
**Depends on:** Phase 3
**Enables:** Phases 6, 9
**Details:** Implement `post_message`, `get_messages`, `search_by_embedding`, `get_pending_decisions`, `acknowledge_message`, `answer_question`, `store_embedding`, `get_trash`, `restore_messages`, `purge_expired_trash`, `get_promotable_messages` (SPEC §21.2). `search_by_embedding` branches on `_VEC_AVAILABLE`: vec0 `vec_distance_cosine` when present, else `ORDER BY ts DESC LIMIT k`. Respect the `_get_write_lock(conn)` pattern for all writes.
**Verify:** `python -m pytest tests/ -q -k comms`

### Phase 5: Embedding worker   ← Conversation: 1
**File:** `src/pathly_orchestrator/runner/embeddings.py` — CREATE
**Done when:** `embed("hello")` returns a 384-float vector and the model loads only once.
**Delivers stories:** S1.2
**Depends on:** Phase 1
**Enables:** Phase 6 (post triggers embedding), Phase 9 (retrieval embeds the task)
**Details:** Lazy-load `SentenceTransformer("all-MiniLM-L6-v2")` into a module global; `embed(text) -> list[float]`. Add `embed_async(message_id, text)` that runs `embed` in a daemon thread and calls `store_embedding`. Add `warm()` that triggers the one-time load (called at server startup in Conv 2). Guard empty text.
**Verify:** `python -c "from pathly_orchestrator.runner.embeddings import embed; print(len(embed('hi')))"`  → prints `384`

---

### Phase 6: Comms HTTP blueprint   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server/blueprints/comms.py` — CREATE
**Done when:** all 8 routes respond and `POST /comms/post` then `GET /comms` round-trips a message.
**Delivers stories:** S1.3
**Depends on:** Phase 4, Phase 5
**Enables:** Phase 8
**Details:** Routes (SPEC §21.3): `POST /comms/post`, `GET /comms`, `POST /comms/search`, `POST /comms/acknowledge`, `POST /comms/answer`, `POST /comms/attach` (stub returning 501 is acceptable this phase — artifacts are Phase 4 of SPEC), `GET /comms/trash`, `POST /comms/restore`. On post: store, call `embed_async`, broadcast (Phase 8). Validate required fields; 400 on missing. Follow the existing blueprint style in `blueprints/runner.py`.
**Verify:** `python -m pytest tests/ -q -k comms_api`

### Phase 7: Register blueprint + model warm-up   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server/app.py` — MODIFY: register comms blueprint; start a daemon warm-up thread
**Done when:** the server starts, `/comms` is reachable, and the embedding model warms in the background without blocking startup.
**Delivers stories:** S1.3, S1.2
**Depends on:** Phase 6
**Enables:** Phase 8
**Details:** `app.register_blueprint(comms_bp)` alongside the others. After registration, `threading.Thread(target=warm, daemon=True).start()` so the first real post isn't blocked by the ~1–2s model load (CONSULTATION §1.2 Risk 3).
**Verify:** start `pathly-fsm-http`, then `curl http://127.0.0.1:8765/comms?feature=demo` returns `[]`

### Phase 8: SSE comms channel   ← Conversation: 2
**File:** `src/pathly_orchestrator/http_server/sse.py` — MODIFY: add `_comms_clients` + `_broadcast_comms()`; **and** `blueprints/streams.py` — MODIFY: add `GET /events/comms`
**Done when:** a curl SSE client on `/events/comms?scope=demo` receives a `COMMS_UPDATE` when a message is posted to `demo`.
**Delivers stories:** S1.4
**Depends on:** Phase 6
**Enables:** Phase 2 of the Studio plan (future)
**Details:** Mirror `_runner_clients` / `_broadcast_runner`. `_comms_clients: dict[str, list]` keyed by scope; `_broadcast_comms(scope, event)` pushes to subscribers and never raises. `GET /events/comms` uses the same generator pattern as `/events/runner`. Wire `_broadcast_comms` into `POST /comms/post`.
**Verify:** terminal A: `curl -N http://127.0.0.1:8765/events/comms?scope=demo` ; terminal B posts a message → A prints a `COMMS_UPDATE` line

---

### Phase 9: Board retrieval + FSM injection   ← Conversation: 3
**File:** `src/pathly_orchestrator/runner/comms_context.py` — CREATE; also MODIFY `fsm_ops.py` to call it
**Done when:** posting a message to a feature board then calling `/next_action` yields a `## Communication Board` block containing that message in `agent_hint.instructions`.
**Delivers stories:** S2.1
**Depends on:** Phase 4, Phase 5, Phase 10 (board_scope)
**Enables:** the core value of Phase 1
**Details:** `retrieve_board_context(topic, project_root, task_description, board_scope) -> str`. Embed the task; query feature(k=3)/project(k=2)/global(k=1) for enabled boards only; always union pending decisions + escalations; format the markdown block per SPEC §11. In `fsm_ops.py build_prompt()` (after the `## Pipeline History` block, ~lines 195–199), append the returned block when non-empty. Keep it additive — empty board ⇒ unchanged prompt.
**Verify:** post via curl, run `pathly-fsm-call next-action --flow team --topic demo --project-root <root>`, assert output contains `## Communication Board`

### Phase 10: board_scope storage + filtering   ← Conversation: 3
**File:** `src/pathly_orchestrator/db/queries/app_settings.py` — MODIFY: add `get_board_scope` / `set_board_scope`
**Done when:** setting `{project:false}` for a feature removes project-board messages from its next injection.
**Delivers stories:** S2.2
**Depends on:** Phase 9
**Enables:** per-feature steering
**Details:** Store under `app_settings` key `board_scope:{project_root}:{feature}` as JSON. `get_board_scope` defaults to `{feature:true, project:true, global:true}` when absent. **Do not** store in STATE.json — `write_state()` does a full `INSERT OR REPLACE` and would drop the key (CONSULTATION §1.2 Risk 2). `retrieve_board_context()` reads board_scope and filters which boards it queries.
**Verify:** `python -m pytest tests/ -q -k board_scope`

## Prerequisites
- Python 3.10+ environment with the package installed editable (`pip install -e .`)
- `~/.pathly/pathly.db` writable (created on first `get_db()`)
- Platform SQLite built with `enable_load_extension` (else recency fallback path is exercised)

## Key Decisions
- **sqlite-vec over a separate vector service** — no new process; fits the existing single-DB model (SPEC §6.1).
- **board_scope in `app_settings`, not STATE.json** — avoids the `write_state()` full-replace merge bug (CONSULTATION §1.2 Risk 2).
- **Extension load before migrations** — the vec0 virtual table cannot be created otherwise (CONSULTATION §1.2 Risk 1).
- **Graceful degradation** — missing sqlite-vec ⇒ recency-only retrieval, never a hard failure (CONSULTATION §1.3).
- **Agents write to their own feature board only** — project/global writes need human confirmation; keeps high-scope boards high-signal (CONSULTATION §1.4 Q1). Enforced as a convention in Phase 1; hard-enforced when skills land (Phase 3 plan).
- **Embedding async + warm at startup** — `/comms/post` never blocks on the model (CONSULTATION §1.2 Risk 3).
