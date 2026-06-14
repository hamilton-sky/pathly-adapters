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

---

## Conversation 4: Retrieval correctness — PRs 1–4 (Phases 1.4a–d)

**Stories delivered:** S1.4a, S1.4b, S1.4c, S1.4d

**Why this comes first:** The Phase 1 retrieval has active correctness bugs — reversed decisions
still get injected, noise dilutes the k=3 slot, governance and soft context are indistinguishable.
These must be fixed before adding hybrid search (Conv 5), or hybrid search finds stale decisions
faster and more reliably, which is worse than the current state.

**Prompt to paste:**
```
Read pathly/plans/comms-board/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Conversation 4 (Phases 1.4a–d) from pathly/plans/comms-board/IMPLEMENTATION_PLAN.md.
Conversations 1–3 are complete. The Phase 1 backend is fully deployed and tested.

This conversation fixes four correctness issues in the already-deployed retrieval layer.
Read IMPLEMENTATION_PLAN.md "Phase 1.4" section in full. Also read docs/BOARD_RETRIEVAL_IMPROVEMENTS.md
for background on each PR.

**IMPORTANT codebase facts to know before you start:**
- New columns go in `_add_additive_migrations()` in `db/migrations.py` as `(table, col, ctype)` tuples.
  The helper already guards with try/except OperationalError — do NOT write standalone ALTER TABLE.
- `embed()` in `runner/embeddings.py` returns `list[float] | None` — always check for None.
- The comms blueprint does NOT use `@require_secret` — auth is at middleware level. Do not add it.
- `get_pending_decisions()` in `db/queries/comms.py` is at line ~118. Read it before editing.
- `retrieve_board_context()` in `runner/comms_context.py` builds the prompt block at lines ~214–240.
  Read it fully before restructuring.

**Before editing anything:** glob/read every file listed below to confirm paths and understand
existing code. Correct any discrepancy between the plan paths and reality before editing.

Phase 1.4a — PR1: superseded_by column + supersede route
- `db/migrations.py` — add `("comms_messages", "superseded_by", "TEXT")` tuple to
  `_add_additive_migrations()`. Do NOT write a standalone ALTER TABLE.
- `db/queries/comms.py` — in `get_pending_decisions()`, add
  `AND (superseded_by IS NULL OR superseded_by = '')` to the WHERE clause.
  Add new function `supersede_message(conn, old_id, new_id) -> str` (see Phase 1.4a in
  IMPLEMENTATION_PLAN.md for the full implementation).
- `http_server/blueprints/comms.py` — add `POST /comms/supersede` route. Body: {old_id, new_id}.
  Returns 200 on success, 404 if old_id not found, 409 if already superseded. No @require_secret.

Phase 1.4b — PR2: write-time curation
- `http_server/blueprints/comms.py` — add `_EMBED_TYPES` frozenset at module level:
  {"decision","discovery","constraint","warning","escalation","artifact"}
  In `comms_post()`, find the unconditional `_embed_async(message_id, text)` call (~line 82)
  and wrap it: `if msg_type in _EMBED_TYPES: _embed_async(message_id, text)`

Phase 1.4c — PR3: labeled governance/semantic channels
- `db/queries/comms.py` — add `get_active_escalations(conn, boards, scopes)` function.
  Follows same signature pattern as `get_pending_decisions()`. WHERE type='escalation'
  AND status='pending' AND deleted_at IS NULL AND (superseded_by IS NULL OR superseded_by = '').
- `runner/comms_context.py` — restructure the prompt block (currently: Decisions / Recent context /
  Open questions sections) into two labeled channels:
  🔒 Governance (decisions + escalations, always applies, injected deterministically)
  💡 Context (semantic matches, labeled as advisory — verify before acting)
  Escalations move from the retrieval pool to the governance channel.
  See IMPLEMENTATION_PLAN.md Phase 1.4c and SPEC §27 for the exact output format.

Phase 1.4d — PR4: remove dead promotion code (bundle with 1.4a since migration is open)
- `db/queries/comms.py` — delete the `get_promotable_messages()` function entirely (lines ~257–269).
  The promoted_to/promoted_from/original_scope columns stay in the schema — add a comment in the
  CREATE TABLE statement in migrations.py marking them "reserved for future promotion feature".
- If `db/queries/__init__.py` re-exports `get_promotable_messages`, remove that export.

Architectural rules:
- db/ must not import runner/ or http_server/. runner/ may import db/.
- Use `_get_write_lock(conn)` for all writes in db/queries/.
- Do not change any test that is currently passing — only add new tests.
- Do not touch: runner/embeddings.py, sse.py, streams.py, app.py, fsm_ops.py,
  any Studio/ file, any adapter _meta/ file.

Verify:
  python -m pytest tests/ -q -k "comms_supersede or comms_embed_curation or comms_context_channels"
  AND:
  # PR1: post old decision, post new, supersede old, run next_action → old absent
  # PR2: post a 'status' message, check comms_embeddings — no row for its id
  # PR3: run /next_action → response contains "🔒 Governance" and "💡 Context"
  # PR4: python -c "from pathly_orchestrator.db.queries.comms import get_promotable_messages"
  #        → ImportError  (no pytest test name — this import check is the verify step)

After done, update pathly/plans/comms-board/PROGRESS.md phases 1.4a–d to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.
```

**Expected output:** The retrieval layer is now correct:
- Superseded decisions are excluded from injection
- Only high-value message types have embedding vectors
- Agent prompts clearly distinguish hard governance rules from soft advisory context
- Dead `get_promotable_messages()` code is gone
**Files touched:** `db/migrations.py`, `db/queries/comms.py`, `http_server/blueprints/comms.py`, `runner/comms_context.py`

---

## Conversation 5: Hybrid search + write permissions (Phases 11–13)

**Stories delivered:** S3.1, S3.2

> **Note:** Phase 14 (DAG tasks) is deferred — see IMPLEMENTATION_PLAN.md Phase 14 note.
> It will be implemented as part of Phase 3 skill integration when the builder skill is
> updated to call `GET /comms/tasks?ready=true`.

**Prompt to paste:**
```
Read pathly/plans/comms-board/FEATURE_INDEX.md first to orient yourself and verify codebase paths.

Implement Comms Board Conversation 5 (Phases 11–13) from pathly/plans/comms-board/IMPLEMENTATION_PLAN.md.
Conversations 1–4 are complete. Phase 1.4 correctness fixes are deployed (superseded_by column exists,
_EMBED_TYPES curation is active, governance/semantic channels are live, dead code is removed).

Context docs: SPEC.md §26 (hybrid BM25+semantic, RRF), §27 (role-based write permissions).
Read those two sections in full before editing anything.

**IMPORTANT codebase facts to know before you start:**
- New columns go in `_add_additive_migrations()` as (table, col, ctype) tuples — NOT standalone ALTER TABLE.
- `search_by_embedding()` signature is `(conn, embedding, boards, scopes, k=6)` — mirror this in
  `search_by_keyword(conn, query_text, boards, scopes, k)` and
  `search_by_hybrid(conn, query_text, query_embedding, boards, scopes, k)`.
  `query_embedding` is `list[float] | None` — handle None gracefully (fall back to keyword-only).
- `_FTS_AVAILABLE` goes in `db/connection.py` alongside `_VEC_AVAILABLE` (same pattern).
- The comms blueprint does NOT use `@require_secret` — auth is middleware-level.
- `embed()` returns `list[float] | None` — callers must not assume a non-None return.

**Before editing anything:** read db/queries/comms.py fully to understand search_by_embedding
(the hybrid function must follow the exact same signature convention). Read blueprints/comms.py
fully — the write-permission check goes inside comms_post() after from_agent and board are parsed.

Phase 11 — FTS5 virtual table + hybrid search helpers:
- `src/pathly_orchestrator/db/connection.py` — add `_FTS_AVAILABLE` module-level flag.
  Place the probe AFTER the `_run_migrations(conn)` call — NOT after the sqlite-vec load block,
  because `comms_fts` does not exist yet when the sqlite-vec block runs (migrations create it).
  Probe: `conn.execute("SELECT * FROM comms_fts LIMIT 0")` in a try/except;
  set `_FTS_AVAILABLE = True/False`. Export alongside `_VEC_AVAILABLE`.
- `src/pathly_orchestrator/db/migrations.py` — in `_run_migrations()`, after the comms_embeddings
  vec0 creation block, add a guarded FTS5 creation:
    CREATE VIRTUAL TABLE IF NOT EXISTS comms_fts
    USING fts5(text, content=comms_messages, content_rowid=rowid, tokenize='porter ascii')
  Wrap in try/except Exception: pass (same pattern as comms_embeddings).
- `src/pathly_orchestrator/db/queries/comms.py` — import `_FTS_AVAILABLE` from ..connection.
  Add `search_by_keyword(conn, query_text, boards, scopes, k=6)` and
  `search_by_hybrid(conn, query_text, query_embedding, boards, scopes, k=6)`.
  See IMPLEMENTATION_PLAN.md Phase 11 for the full implementation of both functions.
  RRF constant: _RRF_K = 60. Hybrid falls back to search_by_embedding alone when _FTS_AVAILABLE=False.

Phase 12 — mode param in search route + hybrid default in retrieval:
- `src/pathly_orchestrator/http_server/blueprints/comms.py` — in comms_search(), read optional
  `mode` field from request body (default 'hybrid'; valid: 'hybrid'|'semantic'|'keyword').
  Branch on mode to call search_by_hybrid, search_by_embedding, or search_by_keyword.
  Mode='semantic' must return identical results to the current code path (no regression).
- `src/pathly_orchestrator/runner/comms_context.py` — in retrieve_board_context(), replace the
  `search_by_embedding(conn, ...)` calls with `search_by_hybrid(conn, task_description, task_embedding, ...)`.
  task_description is already available as the function parameter; task_embedding is already computed.

Phase 13 — Role-based write permissions:
- `src/pathly_orchestrator/http_server/blueprints/comms.py` — add at module level:
    _PROJECT_WRITERS = frozenset({"tester","reviewer","explorer","architect","planner","designer","director","human"})
    _GLOBAL_WRITERS  = frozenset({"director","human"})
    def _check_write_permission(from_agent, board) -> bool: ...
  In comms_post(), add the permission check after board and from_agent are resolved.
  Return 403 JSON: {"error":"Role '<role>' cannot write to '<board>' scope","allowed_roles":[...]}.
  Add GET /comms/permissions?project_root=<root> route (returns resolved permission table).
- `src/pathly_orchestrator/db/queries/app_settings.py` — add get_write_permissions(conn, project_root)
  and set_write_permissions(conn, project_root, overrides). Store under key write_permissions:{project_root}.
  get_write_permissions returns the default table merged with any stored project overrides.
  See IMPLEMENTATION_PLAN.md Phase 13 for the full design.

Architectural rules:
- db/ must not import runner/ or http_server/.
- Use _get_write_lock(conn) for all writes.
- mode='semantic' in the search route must be a true no-op regression test: identical output to
  the pre-Phase-12 code path.
- Do not change any currently-passing test.

Do NOT touch: runner/embeddings.py, sse.py, streams.py, app.py, fsm_ops.py,
any Studio/ file, any adapter _meta/ file.
Do NOT implement Phase 14 (DAG tasks) — it is explicitly deferred.

Verify:
  python -m pytest tests/ -q -k "comms_hybrid or comms_search_mode or comms_write_perm"
  AND:
  # Post a decision containing a specific identifier
  curl -X POST http://127.0.0.1:8765/comms/post \
    -H 'Content-Type: application/json' \
    -d '{"feature":"demo","from":"human","type":"decision","text":"setupWebGL must use WebGL2 context"}'
  # Hybrid search should rank it first for exact-id query
  curl -X POST http://127.0.0.1:8765/comms/search \
    -H 'Content-Type: application/json' \
    -d '{"feature":"demo","query":"setupWebGL","k":3}'
  # → first result text contains "setupWebGL"

  # Permission gate
  curl -X POST http://127.0.0.1:8765/comms/post \
    -H 'Content-Type: application/json' \
    -d '{"board":"global","scope":"global","from":"builder","type":"decision","text":"test"}'
  # → 403 {"error":"Role 'builder' cannot write to 'global' scope","allowed_roles":["director","human"]}

  # Semantic mode must still work (regression)
  curl -X POST http://127.0.0.1:8765/comms/search \
    -H 'Content-Type: application/json' \
    -d '{"feature":"demo","query":"auth bug","mode":"semantic","k":3}'
  # → 200, same results as before Phase 12

After done, update pathly/plans/comms-board/PROGRESS.md phases 11–13 to DONE and S3.1/S3.2 to DONE.

If verification fails and the fix requires out-of-scope changes, stop and report.
If fundamentally broken, rollback with git checkout on affected files and retry.

---

## Conversation 6 — Backend Handoff (no code changes)

**Scope:** RETRO + completion signal. Zero source file edits. PROGRESS.md only.  
**Prerequisite:** Conversations 1–5 all complete and verified.  
**Purpose:** Close the backend phase cleanly so the team pipeline marks this feature DONE and
the user knows the frontend (`comms-board-studio`) is the next step — but only after design
consultation.

---

You are the **orchestrator** for the `comms-board` backend feature.
Conversations 1–5 are complete. Your job in this conversation is:

1. Read `pathly/plans/comms-board/PROGRESS.md` and confirm all Conv 1–5 phases show DONE.

2. Write a RETRO summary to `pathly/plans/comms-board/RETRO.md`:

```
# Comms Board — Backend RETRO

## What shipped
- Phase 1 (Convs 1–3): DB schema, embeddings, HTTP API (8 routes), SSE, FSM injection, board_scope control
- Phase 1.4 (Conv 4): superseded_by suppression, write-time curation (_EMBED_TYPES), labeled governance/semantic channels, dead promotion code removed
- Phase 1.5 (Conv 5): hybrid BM25+semantic search (FTS5+cosine via RRF), mode param on /comms/search, role-based write permissions

## What is NOT shipped (explicitly deferred)
- Phase 14 DAG tasks — bundles with Phase 3 skill integration (comms-board-skills plan)
- Phase 2 Studio UI — pending design consultation (comms-board-studio plan)
- Phase 5 Board-Storm — long-term (board-storm plan)
- Phase 4 Command Center — long-term (comms-board-command-center plan)

## Backend is fully curl-testable
All deliverables work with zero Studio/Electron changes.
Run: python -m pytest tests/ -q -k comms

## Next step
Design consultation on the Studio board UI before opening comms-board-studio.
Do NOT start comms-board-studio until design is confirmed.

## BACKEND_COMPLETE
Signal: BACKEND_COMPLETE
Date: <today>
```

3. Update `pathly/plans/comms-board/PROGRESS.md`:
   - Change Conv 6 status row to DONE
   - Change the top-level status line to: `Phase 1 COMPLETE · Phase 1.4 COMPLETE · Phase 1.5 COMPLETE · BACKEND DONE · Frontend PENDING DESIGN`

4. Log to `pathly/plans/comms-board/EVENTS.jsonl`:
```json
{"event":"BACKEND_COMPLETE","plan":"comms-board","convs_done":[1,2,3,4,5,6],"next":"comms-board-studio (pending design consultation)"}
```

5. Output to the user:
```
✅ BACKEND COMPLETE

All comms board backend phases are done and verified.

What shipped:
  • /comms/* HTTP API (8 routes)
  • Semantic embedding + retrieval in every /next_action
  • Retrieval correctness (superseded decisions, curation, labeled channels)
  • Hybrid BM25+semantic search (FTS5 + cosine RRF)
  • Role-based write permissions

What's next:
  → Design consultation on Studio board UI
  → When ready: open comms-board-studio as a new feature
  → Do NOT start Studio UI until design is confirmed

Deferred (not forgotten):
  → DAG task decomposition (Phase 14) — bundles with comms-board-skills
```

Do not edit any Python source files. Do not run tests. PROGRESS.md and RETRO.md and EVENTS.jsonl are the only files you touch.
```

**Expected output:** Phase 1.5 hybrid retrieval and permissions are working:
- `POST /comms/search` supports `mode=hybrid|semantic|keyword`; default is hybrid (BM25 + cosine RRF)
- Exact identifiers like function names and error codes rank first under hybrid mode
- `POST /comms/post` enforces scope write limits per agent role (403 on violation)
- `GET /comms/permissions` returns the resolved permission table
**Files touched:** `db/connection.py`, `db/migrations.py`, `db/queries/comms.py`,
`http_server/blueprints/comms.py`, `runner/comms_context.py`, `db/queries/app_settings.py`
