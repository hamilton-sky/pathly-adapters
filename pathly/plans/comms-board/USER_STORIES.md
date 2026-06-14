---
name: User Stories
---
# Comms Board (Phase 1 — Backend Core) — User Stories

## Context

Today every Pathly agent starts almost blind — it reads the plan files and the last few
AGENT_DONE summaries, but never sees what the human said mid-run, what the reviewer
discovered, or what was decided in conversation. There is no persistent, bidirectional,
searchable channel between the human and the agents across a feature's lifecycle.

Phase 1 builds the **backend** of the communication board: a vector-searchable message
store (sqlite-vec) at three scopes (feature / project / global), HTTP endpoints to post
and query it, and FSM injection so every agent receives the most relevant board context
in its prompt. This phase ships value with **zero Studio changes** — a human can steer
agents by posting to the board via curl, and the next agent reads it automatically.

---

## Stories

### Story 1.1: Vector-searchable message store
**As a** Pathly developer, **I want** comms messages stored in a SQLite table with a
sqlite-vec embedding index, **so that** board context persists across runs and can be
retrieved by semantic similarity, not just recency.

**Acceptance Criteria:**
- [ ] `comms_messages` table exists with all schema columns from SPEC §21.1 (board, scope, from_agent, to_agent, type, text, status, lifecycle + artifact + task fields)
- [ ] `comms_embeddings` vec0 virtual table exists with `FLOAT[384]` embedding column
- [ ] sqlite-vec extension loads at connection time **before** migrations run
- [ ] If sqlite-vec fails to load, the server still starts and logs a warning (graceful degradation)
- [ ] `db/queries/comms.py` exposes post / get / search / acknowledge / trash / restore / promote helpers

**Edge Cases:**
- sqlite-vec extension unavailable on the platform → recency-only fallback, no crash
- A message with no embedding yet (async pending) → still returned by exact-match queries

**Delivered by:** Phase 1–4 → Conversation 1

---

### Story 1.2: Message embeddings for semantic search
**As a** Pathly developer, **I want** each posted message embedded with all-MiniLM-L6-v2,
**so that** `/comms/search` and FSM retrieval return semantically relevant messages.

**Acceptance Criteria:**
- [ ] `runner/embeddings.py` exposes `embed(text) -> list[float]` returning a 384-dim vector
- [ ] The model loads once and is cached in memory (not re-loaded per call)
- [ ] Embedding runs in a background thread so `/comms/post` returns immediately
- [ ] A posted message is searchable by vector similarity within ~200ms of posting
- [ ] Searching a stored message by a paraphrase of its text returns it in the top results

**Edge Cases:**
- Model not yet warm on first post → message stored immediately, embedded when model ready
- Empty / whitespace-only text → skip embedding, store message anyway

**Delivered by:** Phase 5 → Conversation 1

---

### Story 1.3: HTTP API to post and query the board
**As a** human (or Studio), **I want** HTTP endpoints to post, list, and search board
messages, **so that** I can steer agents and read their updates without editing files.

**Acceptance Criteria:**
- [ ] `POST /comms/post` stores a message, triggers async embedding, returns its id
- [ ] `GET /comms` returns messages filtered by feature / board / type / status
- [ ] `POST /comms/search` returns top-k semantically similar messages across requested boards
- [ ] `POST /comms/acknowledge` marks a message read by an agent
- [ ] `POST /comms/answer` posts an answer reply linked to a question
- [ ] `GET /comms/trash` + `POST /comms/restore` cover the soft-delete lifecycle
- [ ] All routes validate input and return clear 400s on bad payloads
- [ ] The comms blueprint is registered in `app.py`

**Edge Cases:**
- Search with no embeddings present → returns recency-ordered results, not an error
- Posting to a non-existent feature scope → allowed (scopes are created implicitly)

**Delivered by:** Phase 6–7 → Conversation 2

---

### Story 1.4: Real-time board updates over SSE
**As a** human using Studio (future), **I want** board changes broadcast over SSE,
**so that** the UI can show new messages and answers in real time.

**Acceptance Criteria:**
- [ ] `sse.py` has a `_comms_clients` registry and a `_broadcast_comms(scope, event)` helper
- [ ] `POST /comms/post` broadcasts a `COMMS_UPDATE` event after storing
- [ ] `GET /events/comms?scope=<scope>` streams `COMMS_UPDATE` events for that scope
- [ ] The SSE stream follows the same pattern as the existing `/events/runner` stream
- [ ] Disconnecting a client removes it from the registry (no leak)

**Edge Cases:**
- A broadcast with no subscribed clients → no-op, never raises
- Embedding-complete update → optional second broadcast; must not duplicate the message in the UI model

**Delivered by:** Phase 8 → Conversation 2

---

### Story 2.1: Board context injected into agent prompts
**As a** Pathly agent, **I want** the most relevant board messages injected into my prompt
at `/next_action`, **so that** I start every stage knowing the team's decisions, the
human's constraints, and prior discoveries.

**Acceptance Criteria:**
- [ ] `retrieve_board_context()` embeds the next task, queries enabled boards (feature k=3, project k=2, global k=1)
- [ ] Pending `decision` and `escalation` messages are always included regardless of similarity
- [ ] The result is a `## Communication Board` markdown block appended to `agent_hint.instructions`
- [ ] When the board is empty, no block is added (prompt is unchanged from today)
- [ ] At most ~6 retrieved messages plus mandatory decisions are injected (bounded prompt growth)
- [ ] Retrieval adds < ~150ms to a `/next_action` call at expected data volumes

**Edge Cases:**
- sqlite-vec unavailable → recency-ordered messages injected instead (still useful)
- A very large global board → search space capped before vector comparison

**Delivered by:** Phase 9 → Conversation 3

---

### Story 2.2: Per-feature board scope control
**As a** human, **I want** each feature to declare which boards its agents read from,
**so that** a feature can run "clean" (ignore its own board), deviate from project norms,
or break global rules for a spike — without affecting other features.

**Acceptance Criteria:**
- [ ] `get_board_scope(project_root, feature)` returns `{feature, project, global}`, defaulting to all-true when unset
- [ ] `set_board_scope(...)` persists the config (stored in `app_settings`, **not** STATE.json — avoids the write_state merge bug per CONSULTATION §1.2 Risk 2)
- [ ] `retrieve_board_context()` queries only the boards enabled in board_scope
- [ ] Disabling `feature` stops the feature board from being injected for that feature only
- [ ] Changing board_scope takes effect on the next `/next_action`; the current stage is not interrupted

**Edge Cases:**
- board_scope missing for a feature → treated as all-true (backward compatible)
- All three scopes disabled → no board block injected, no error

**Delivered by:** Phase 10 → Conversation 3

---

## Phase 1.5 — Retrieval Quality, Permissions, DAG Tasks

---

### Story 3.1: Hybrid BM25 + semantic retrieval
**As a** Pathly agent, **I want** board searches to combine keyword (BM25) and semantic
(cosine) ranking, **so that** exact identifiers (function names, file paths, error codes)
are found reliably alongside conceptually similar messages.

**Acceptance Criteria:**
- [ ] `comms_fts` FTS5 virtual table exists as a content-table over `comms_messages.text`
- [ ] `search_by_hybrid(conn, query_text, query_embedding, boards, scopes, k)` is in `db/queries/comms.py`
- [ ] RRF score = `1/(60 + rank_bm25) + 1/(60 + rank_semantic)` merges the two ranked lists
- [ ] `POST /comms/search` accepts a `mode` parameter: `hybrid` (default), `semantic`, `keyword`
- [ ] `retrieve_board_context()` uses `hybrid` mode by default
- [ ] A message containing an exact identifier (e.g. `setupWebGL`) is returned when the query
      contains that exact identifier, even if the cosine score would not rank it top-3
- [ ] If FTS5 is unavailable, falls back to semantic-only without error
- [ ] If both FTS5 and sqlite-vec are unavailable, falls back to recency ordering

**Edge Cases:**
- Query contains only stop words ("the is a") → FTS5 returns empty; cosine result still returned
- Message posted but FTS index not yet updated → still returned by cosine path

**Delivered by:** Phase 11–12 → Conversation 5
**SPEC reference:** §26

---

### Story 3.2: Role-based write permissions
**As a** Pathly operator, **I want** agent roles to be limited in which board scopes they
can write to, **so that** the project and global boards stay high-signal and are never
accidentally polluted by feature-scoped agents.

**Acceptance Criteria:**
- [ ] `POST /comms/post` checks `from_agent` role against `_PROJECT_WRITERS` and `_GLOBAL_WRITERS` frozensets
- [ ] Agents not in `_PROJECT_WRITERS` receive **403 Forbidden** when posting to `board='project'`
- [ ] Only `director` and `human` can post to `board='global'`; all others receive **403**
- [ ] `feature` scope write is unrestricted (any role may write)
- [ ] `GET /comms/permissions?project_root=<root>` returns the resolved permission table as JSON
- [ ] Project-level overrides can be stored in `app_settings` under `write_permissions:{project_root}`
      and are merged with the default table at request time
- [ ] The 403 response body includes the role, the target scope, and a hint about which roles are allowed

**Edge Cases:**
- `from_agent` is missing or empty → treated as unknown role (feature-only access)
- `from_agent='human'` → always allowed to any scope
- Project override grants `builder` project-write → builder succeeds for that project

**Delivered by:** Phase 13 → Conversation 5
**SPEC reference:** §27

---

### Story 3.3: DAG task decomposition
**As a** builder agent, **I want** to query which tasks are currently unblocked (all
their dependencies done), **so that** I can work in the correct dependency order within
the BUILD stage without reading the full task list and guessing.

**Acceptance Criteria:**
- [ ] `comms_messages` has a `depends_on TEXT DEFAULT '[]'` column (JSON array of message IDs)
- [ ] `get_ready_tasks(conn, board, scope)` returns tasks of type `task` and `task_status='pending'`
      whose every `depends_on` ID has `task_status='done'`; tasks with `depends_on=[]` are always ready
- [ ] `GET /comms/tasks?feature=<name>&ready=true` returns only ready tasks
- [ ] `GET /comms/tasks?feature=<name>&status=pending` returns all pending tasks (with and without met deps)
- [ ] `POST /comms/tasks/complete` sets `task_status='done'` and broadcasts `COMMS_UPDATE` over SSE
- [ ] `POST /comms/tasks/complete` is idempotent: completing a done task returns 200 with no change
- [ ] After marking task `t1` done, `GET /comms/tasks?ready=true` reflects that tasks depending
      only on `t1` now appear as ready

**Edge Cases:**
- `depends_on` contains an ID that does not exist → that dependency is treated as not-done
  (task stays blocked)
- Circular dependencies (t1 depends on t2, t2 depends on t1) → neither is ever ready; no error
- Non-task message types ignore `depends_on` (field stored but never evaluated)

**Delivered by:** Phase 14 → Deferred (Phase 3 bundle)
**SPEC reference:** §28
