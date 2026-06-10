---
name: Conversation Guide
---
# Comms Board (Phase 1 — Backend Core) — Conversation Guide

Split into 3 conversations (max 4). Each produces runnable, testable code.
After each conversation, **commit your changes** before starting the next.

---

## Conversation 1: Storage foundation — DB tables + embeddings (Phases 1–5)

**Stories delivered:** S1.1, S1.2

**Prompt to paste:**
```
Read pathly/plans/comms-board/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Conversation 1 (Phases 1–5) from pathly/plans/comms-board/IMPLEMENTATION_PLAN.md.

Context docs in this folder: SPEC.md (§21.1 schema, §21.2 query helpers) and CONSULTATION.md
(§1.2 lists 5 risks — Risk 1 and Risk 4 apply to this conversation). Read those sections before editing.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Correct any discrepancy between the plan's stated paths and reality before proceeding.

Scope:
- Phase 1: `pyproject.toml` — add `sqlite-vec==0.1.6` (pin exactly) and `sentence-transformers>=2.7.0`.
- Phase 2: `src/pathly_orchestrator/db/connection.py` — inside get_db(), AFTER the PRAGMA lines and
  BEFORE _run_migrations(conn), load the sqlite-vec extension with a try/except that sets a
  module-level _VEC_AVAILABLE flag and logs a warning on failure (graceful degradation).
- Phase 3: `src/pathly_orchestrator/db/migrations.py` — add the comms_messages table and the
  comms_embeddings vec0 virtual table using the exact schema in SPEC.md §21.1. Guard both with
  IF NOT EXISTS; skip the vec0 table when _VEC_AVAILABLE is false.
- Phase 4: create `src/pathly_orchestrator/db/queries/comms.py` with the 11 helpers listed in
  SPEC.md §21.2; re-export them from db/queries/__init__.py. search_by_embedding must branch on
  _VEC_AVAILABLE (vec_distance_cosine when present, else ORDER BY ts DESC LIMIT k). Use the
  existing _get_write_lock(conn) pattern for every write.
- Phase 5: create `src/pathly_orchestrator/runner/embeddings.py` with embed(text)->list[float]
  (lazy-load all-MiniLM-L6-v2 into a module global, load once), embed_async(message_id, text)
  (daemon thread → store_embedding), and warm().

Architectural rules to observe:
- Read CLAUDE.md and src/pathly_orchestrator/CLAUDE.md for layer rules before implementing.
- db/ must not import from runner/, supervisor/, or http_server/. (runner/embeddings.py may import db/.)
- Critical ordering: sqlite-vec must load BEFORE migrations run — the vec0 virtual table needs it.
- Stay within the db/ and runner/ layers. Do not touch http_server/ or fsm_ops.py yet.

Do NOT touch: http_server/ (Conv 2), fsm_ops.py (Conv 3), any Studio/ file, any adapter _meta/ file.
Verify: `python -m pytest tests/ -q -k comms` AND
        `python -c "from pathly_orchestrator.runner.embeddings import embed; print(len(embed('hi')))"` prints 384.
After done, update pathly/plans/comms-board/PROGRESS.md phases 1–5 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** The DB layer is complete and testable in isolation — a message can be
posted to `comms_messages`, embedded into `comms_embeddings`, and retrieved by vector search,
all from Python with no HTTP server running. sqlite-vec absence degrades to recency search.
**Files touched:** `pyproject.toml`, `db/connection.py`, `db/migrations.py`, `db/queries/comms.py`, `db/queries/__init__.py`, `runner/embeddings.py`

---

## Conversation 2: HTTP API + SSE (Phases 6–8)

**Stories delivered:** S1.3, S1.4

**Prompt to paste:**
```
Read pathly/plans/comms-board/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Conversation 2 (Phases 6–8) from pathly/plans/comms-board/IMPLEMENTATION_PLAN.md.
Conversation 1 is complete: db/queries/comms.py and runner/embeddings.py exist and are tested.

Context docs: SPEC.md §21.3 (the 8 routes) and §10/§21.4 (SSE). CONSULTATION.md §1.2 Risk 3
(warm the model at startup so the first post does not block). Read those before editing.

**Before editing anything:** glob/read the live repo to confirm every file path below exists.
Study the existing blueprints/runner.py and the _runner_clients / _broadcast_runner code in sse.py
and the /events/runner route in blueprints/streams.py — mirror those patterns exactly.

Scope:
- Phase 6: create `src/pathly_orchestrator/http_server/blueprints/comms.py` with 8 routes
  (POST /comms/post, GET /comms, POST /comms/search, POST /comms/acknowledge, POST /comms/answer,
  POST /comms/attach [may return 501 this phase], GET /comms/trash, POST /comms/restore). On post:
  store via db/queries/comms.py, call embed_async, then broadcast (Phase 8). Validate required
  fields and return 400 on bad input.
- Phase 7: `src/pathly_orchestrator/http_server/app.py` — register the comms blueprint alongside
  the others, then start a daemon thread calling embeddings.warm() so model load never blocks startup.
- Phase 8: `src/pathly_orchestrator/http_server/sse.py` — add _comms_clients dict + _broadcast_comms(scope, event);
  `src/pathly_orchestrator/http_server/blueprints/streams.py` — add GET /events/comms?scope=<scope>
  using the same generator pattern as /events/runner. Wire _broadcast_comms into POST /comms/post.

Architectural rules to observe:
- Read src/pathly_orchestrator/CLAUDE.md layer rules. http_server/ may import db/ and runner/ —
  do those imports lazily inside route handlers, matching the existing blueprint style.
- Do not change the comms query helpers or the embeddings module from Conv 1 except to call them.

Do NOT touch: db/migrations.py, db/queries/comms.py, runner/embeddings.py (done in Conv 1),
fsm_ops.py (Conv 3), any Studio/ file, any adapter _meta/ file.
Verify: start `pathly-fsm-http`, then
        `curl -X POST http://127.0.0.1:8765/comms/post -H "Content-Type: application/json" -d '{"feature":"demo","from":"human","type":"nudge","text":"focus on Editor first"}'`
        then `curl "http://127.0.0.1:8765/comms?feature=demo"` returns that message.
        SSE: `curl -N "http://127.0.0.1:8765/events/comms?scope=demo"` prints COMMS_UPDATE when a new message is posted.
After done, update pathly/plans/comms-board/PROGRESS.md phases 6–8 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** The board is fully usable over HTTP — a human can post, list, and search
messages with curl, and an SSE client receives real-time COMMS_UPDATE events. The embedding
model warms in the background at server start.
**Files touched:** `http_server/blueprints/comms.py`, `http_server/app.py`, `http_server/sse.py`, `http_server/blueprints/streams.py`

---

## Conversation 3: FSM injection + board_scope (Phases 9–10)

**Stories delivered:** S2.1, S2.2

**Prompt to paste:**
```
Read pathly/plans/comms-board/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Conversation 3 (Phases 9–10) from pathly/plans/comms-board/IMPLEMENTATION_PLAN.md.
Conversations 1–2 are complete: the DB layer, embeddings, HTTP API, and SSE all work.

This conversation delivers the core value: agents receive board context in their prompts.
Context docs: SPEC.md §11 (the exact ## Communication Board markdown format), §6.3 (retrieval query),
§16.4 (board_scope). CONSULTATION.md §1.2 Risk 2 (store board_scope in app_settings, NOT STATE.json —
write_state() does a full INSERT OR REPLACE and would drop the key). Read those before editing.

**Before editing anything:** glob/read the live repo. Read fsm_ops.py build_prompt() fully and find
where the `## Pipeline History` block is appended (around lines 195–199) — the new block goes after it.
Read db/queries/app_settings.py to match its get/set style.

Scope:
- Phase 10 (do first — Phase 9 depends on it): `src/pathly_orchestrator/db/queries/app_settings.py` —
  add get_board_scope(project_root, feature) returning {feature, project, global} defaulting to all-true
  when absent, and set_board_scope(...). Store under app_settings key board_scope:{project_root}:{feature}
  as JSON. Do NOT add board_scope to STATE.json.
- Phase 9: create `src/pathly_orchestrator/runner/comms_context.py` with
  retrieve_board_context(topic, project_root, task_description, board_scope) -> str. Embed the task
  description; for each ENABLED board query feature(k=3)/project(k=2)/global(k=1) via search_by_embedding;
  always union pending decisions + escalations (get_pending_decisions); format the ## Communication Board
  markdown block exactly per SPEC.md §11; return "" when there is nothing. Then in fsm_ops.py build_prompt(),
  after the ## Pipeline History block, read board_scope via get_board_scope and append the returned block
  when non-empty. Keep it additive: empty board ⇒ prompt identical to today.

Architectural rules to observe:
- Read src/pathly_orchestrator/CLAUDE.md. runner/ may import db/. fsm_ops.py may import runner/.
- The block must be bounded: at most ~6 retrieved messages plus mandatory decisions.
- Do not alter the existing ## Current task or ## Pipeline History blocks — only append after them.

Do NOT touch: db/migrations.py, db/queries/comms.py, runner/embeddings.py, http_server/* (prior convs),
any Studio/ file, any adapter _meta/ file.
Verify: `python -m pytest tests/ -q -k "comms_context or board_scope"` AND manual:
        post a message to feature "demo" via curl, then
        `pathly-fsm-call next-action --flow team --topic demo --project-root <repo root>`
        and confirm the response agent_hint.instructions contains "## Communication Board" with the message.
        Then set board_scope {project:false} for demo and confirm project-board messages drop out.
After done, update pathly/plans/comms-board/PROGRESS.md phases 9–10 to DONE and Status to COMPLETE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** Posting to the board steers the next agent — `/next_action` injects a
`## Communication Board` block into `agent_hint.instructions`, filtered by the feature's
board_scope. Phase 1 backend is complete and delivers value with zero Studio changes.
**Files touched:** `runner/comms_context.py`, `fsm_ops.py`, `db/queries/app_settings.py`
