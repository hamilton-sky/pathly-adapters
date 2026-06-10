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
