---
name: Architecture Proposal
---
# Comms Board (Phase 1 — Backend Core) — Architecture Proposal

## Problem Statement

Pathly agents start each stage without the human's mid-run guidance, prior agents'
discoveries, or any organizational memory. We need a persistent, bidirectional,
semantically-searchable channel — and Phase 1 must deliver it on the backend without
touching Studio, so it ships fast and proves the concept via curl.

## Proposed Solution

Add a vector-searchable message store to the existing `~/.pathly/pathly.db` using the
sqlite-vec extension, an embedding worker, HTTP endpoints, an SSE channel, and a single
new context block injected into every agent prompt at `/next_action`. The FSM state
machine is unchanged — the board is purely additive context.

## Layer Breakdown

```
Layer A   (pathly/plans/comms-board — this plan)
     │  feature definition + acceptance criteria
     ▼
Layer B   (db/  — connection.py, migrations.py, queries/comms.py)
     │  storage: comms_messages + comms_embeddings (vec0)
     ▼
Layer C   (runner/  — embeddings.py, comms_context.py)
     │  semantics: embed(), retrieve_board_context()
     ▼
Layer D   (http_server/  — blueprints/comms.py, sse.py, streams.py)
     │  API + realtime: /comms/*, /events/comms
     ▼
Injection (fsm_ops.py build_prompt → agent_hint.instructions)
     │  ## Communication Board block
     ▼
Runtime / the next agent
```

## Key Design Decisions

### Decision 1: sqlite-vec inside the existing DB
- **Options considered:** (A) sqlite-vec virtual table in pathly.db, (B) standalone vector service (Chroma/Qdrant), (C) flat-file + brute-force cosine
- **Chosen:** A
- **Rationale:** No new process, no new dependency surface beyond a wheel, no config. Pathly already centralizes all state in pathly.db; backups and the connection cache come for free. (SPEC §6.1)

### Decision 2: board_scope in app_settings, not STATE.json
- **Options considered:** (A) STATE.json field, (B) app_settings key-value, (C) dedicated table
- **Chosen:** B
- **Rationale:** `write_state()` does a full `INSERT OR REPLACE` of the serialized state dict — any key the caller omits is silently dropped. Storing board_scope in `app_settings` (which already exists and supports arbitrary keys) sidesteps the merge hazard entirely. A dedicated table is overkill for one small JSON blob per feature. (CONSULTATION §1.2 Risk 2)

### Decision 3: Extension load ordering
- **Options considered:** (A) load sqlite-vec before migrations, (B) lazy-load on first vector query
- **Chosen:** A
- **Rationale:** The migration creates `comms_embeddings USING vec0(...)`, which fails unless the extension is already loaded on that connection. Loading in `get_db()` before `_run_migrations()` is the only correct order. (CONSULTATION §1.2 Risk 1)

### Decision 4: Async embedding + startup warm
- **Options considered:** (A) embed synchronously in the request, (B) async daemon thread + warm at startup
- **Chosen:** B
- **Rationale:** The model load is ~1–2s and embedding is ~tens of ms. Synchronous embedding would make the first `/comms/post` feel broken. Warming at startup and embedding off-thread keeps posts instant. (CONSULTATION §1.2 Risk 3)

### Decision 5: Graceful degradation when sqlite-vec is absent
- **Options considered:** (A) hard-fail server start, (B) recency-only fallback
- **Chosen:** B
- **Rationale:** A missing extension on some platform must not break the whole orchestrator. `_VEC_AVAILABLE=False` routes all search to `ORDER BY ts DESC` — less smart, still useful, never down. (CONSULTATION §1.3)

## Key Components
- `db/migrations.py` additions — `comms_messages` table, `comms_embeddings` vec0 virtual table
- `db/queries/comms.py` (new) — 11 helpers: post / get / search / acknowledge / answer / store_embedding / trash / restore / purge / promotable / pending_decisions
- `runner/embeddings.py` (new) — `embed()`, `embed_async()`, `warm()` over all-MiniLM-L6-v2
- `http_server/blueprints/comms.py` (new) — 8 routes
- `http_server/sse.py` additions — `_comms_clients`, `_broadcast_comms()`
- `runner/comms_context.py` (new) — `retrieve_board_context()` → `## Communication Board` block
- `db/queries/app_settings.py` additions — `get_board_scope()`, `set_board_scope()`

## Interface Design
```
embed(text: str) -> list[float]                 # 384 dims
retrieve_board_context(topic, project_root, task_description, board_scope) -> str
get_board_scope(project_root, feature) -> {"feature":bool,"project":bool,"global":bool}

POST /comms/post     {feature, from, to?, type, text, options?, reply_to?, board?} -> {id}
GET  /comms          ?feature&board?&type?&status?&limit? -> [message]
POST /comms/search   {query, feature?, k?, boards?} -> [message+score]
GET  /events/comms   ?scope=<scope> -> SSE COMMS_UPDATE stream
```

## Risks
- **sqlite-vec version drift** → pin `==0.1.6`; the `FLOAT[384]` vec0 syntax is version-specific. (Risk 4)
- **Embedding model download on a cold machine** → warm thread at startup; first post still works (stored now, embedded soon). (Risk 3)
- **Prompt bloat from too many injected messages** → hard caps (3/2/1) + compact decision lines; bounded growth is an acceptance criterion.
- **Layer leakage** → db/ must not import runner/http_server; enforced by the package's existing layer rules and reviewer check.
