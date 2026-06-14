---
name: Progress
---
# Comms Board — Progress

## Status: Phase 1 COMPLETE · Phase 1.4 COMPLETE · Phase 1.5 TODO · Frontend PENDING DESIGN

> **This plan is backend-only.** No Studio/Electron code is touched here.
>
> **Phase 1** (Backend Core — Convs 1–3): all phases done · reviewed · 469 passed / 6 pre-existing failures  
> **Phase 1.4** (Retrieval Correctness — Conv 4): COMPLETE — superseded_by suppression, embed curation, governance/context channels, dead code removed  
> **Phase 1.5** (Retrieval Quality + Permissions — Conv 5): not started — ship after Phase 1.4  
> **Conv 6** (Backend handoff): no code — writes RETRO + emits BACKEND_COMPLETE, then this plan is DONE  
> **Phase 14 DAG**: deferred — bundles with Phase 3 skill integration  
> **Frontend gate**: do NOT open `comms-board-studio` until design consultation complete

> **Review note (board/scope alignment):** Conv 2/3 originally stored `board`=feature-name,
> `scope`=tier — inverted from SPEC §21.1 (`board`=tier, `scope`=identifier). Fixed in
> `blueprints/comms.py` + `runner/comms_context.py` and re-verified end-to-end (all three
> tiers retrieve with correct labels; HTTP stores `board='feature'`, `scope=<feature name>`).
> Also corrected a latent trash bug (`/comms/trash?scope=feature` would have matched all features).

## Story Status

| Story | Title | Delivered by | Status |
|-------|-------|--------------|--------|
| S1.1 | Vector-searchable message store | Conv 1 | DONE |
| S1.2 | Message embeddings for semantic search | Conv 1 | DONE |
| S1.3 | HTTP API to post and query the board | Conv 2 | DONE |
| S1.4 | Real-time board updates over SSE | Conv 2 | DONE |
| S2.1 | Board context injected into agent prompts | Conv 3 | DONE |
| S2.2 | Per-feature board scope control | Conv 3 | DONE |
| S1.4a | PR1 — superseded_by: fix stale decision injection | Conv 4 | DONE |
| S1.4b | PR2 — write-time curation: stop embedding noise | Conv 4 | DONE |
| S1.4c | PR3 — labeled governance/semantic channels | Conv 4 | DONE |
| S1.4d | PR4 — remove get_promotable_messages() dead code | Conv 4 | DONE |
| S3.1 | Hybrid BM25 + semantic retrieval | Conv 5 | TODO |
| S3.2 | Role-based write permissions | Conv 5 | TODO |
| S3.3 | DAG task decomposition | Deferred (Phase 3 bundle) | TODO |

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1–5 | S1.1, S1.2 | DONE | `python -m pytest tests/ -q -k comms` |
| 2 | 6–8 | S1.3, S1.4 | DONE | `curl POST /comms/post` then `GET /comms` round-trips |
| 3 | 9–10 | S2.1, S2.2 | DONE | `/next_action` output contains `## Communication Board` |
| 4 | 1.4a–d | S1.4a, S1.4b, S1.4c, S1.4d | DONE | `python -m pytest tests/ -q -k "comms_supersede or comms_embed_curation or comms_context_channels"` |
| 5 | 11–13 | S3.1, S3.2 | TODO | `python -m pytest tests/ -q -k "comms_hybrid or comms_search_mode or comms_write_perm"` |
| **6** | — | — | TODO | PROGRESS.md all phases DONE; RETRO written; `BACKEND_COMPLETE` logged |

> ── **BACKEND BOUNDARY** ── Conv 6 is the last conversation in this plan. Frontend work starts in `comms-board-studio` after design consultation.

See **CONVERSATION_PROMPTS.md** for exact prompts to paste in each conversation.

## Phase Detail

| Conv | Phase | File | Description | Done when | Status |
|------|-------|------|-------------|-----------|--------|
| 1 | 1 Dependencies | `pyproject.toml` | Add sqlite-vec==0.1.6 + sentence-transformers | imports run clean | DONE |
| 1 | 2 Load extension | `db/connection.py` | Load sqlite-vec before migrations + fallback flag | `select vec_version()` works | DONE |
| 1 | 3 Migration | `db/migrations.py` | comms_messages + comms_embeddings vec0 | both tables queryable | DONE |
| 1 | 4 Query helpers | `db/queries/comms.py` | post/get/search/ack/trash/restore/promote | post then search returns row | DONE |
| 1 | 5 Embeddings | `runner/embeddings.py` | embed() + async worker + warm() | embed('hi') → 384 floats | DONE |
| 2 | 6 Blueprint | `http_server/blueprints/comms.py` | 8 /comms/* routes | post→get round-trips | DONE |
| 2 | 7 Register + warm | `http_server/app.py` | register bp + startup warm thread | `/comms` reachable | DONE |
| 2 | 8 SSE | `http_server/sse.py` + `blueprints/streams.py` | _comms_clients + /events/comms | client gets COMMS_UPDATE | DONE |
| 3 | 9 Retrieval + inject | `runner/comms_context.py` + `fsm_ops.py` | retrieve_board_context + prompt block | block appears in next_action | DONE |
| 3 | 10 board_scope | `db/queries/app_settings.py` | get/set board_scope + filter | disabling project filters it out | DONE |
| 4 | 1.4a PR1 superseded_by | `db/migrations.py` + `db/queries/comms.py` + `blueprints/comms.py` | superseded_by col + supersede_message() + POST /comms/supersede | stale decision excluded from injection | DONE |
| 4 | 1.4b PR2 curation filter | `http_server/blueprints/comms.py` | _EMBED_TYPES frozenset + conditional embed_async | status msg has no embedding row | DONE |
| 4 | 1.4c PR3 labeled channels | `db/queries/comms.py` + `runner/comms_context.py` | get_active_escalations() + governance/semantic split | 🔒 and 💡 sections appear in injection | DONE |
| 4 | 1.4d PR4 dead code | `db/queries/comms.py` | delete get_promotable_messages() | ImportError on that name | DONE |
| 5 | 11 FTS5 + hybrid helpers | `db/migrations.py` + `db/connection.py` + `db/queries/comms.py` | comms_fts + _FTS_AVAILABLE + search_by_keyword/hybrid | exact-id query ranks first | TODO |
| 5 | 12 Hybrid mode in API + retrieval | `blueprints/comms.py` + `runner/comms_context.py` | mode param + hybrid default in retrieve | /comms/search mode=keyword works | TODO |
| 5 | 13 Write permissions | `blueprints/comms.py` + `db/queries/app_settings.py` | _PROJECT/_GLOBAL_WRITERS + 403 + /comms/permissions | builder→global returns 403 | TODO |
| — | 14 DAG tasks | DEFERRED | see SPEC §28; bundles with Phase 3 skills | t2 ready after t1 complete | DEFERRED |

## Prerequisites
- Python 3.10+, package installed editable (`pip install -e .`)
- `~/.pathly/pathly.db` writable
- SQLite built with `enable_load_extension` (else recency fallback is exercised)

## Blocked By
- Nothing (Conv 4 can start immediately — Phase 1 is fully complete)

## Conv 3 Notes
- Phase 10 implemented first (board_scope storage in app_settings).
- Phase 9 `retrieve_board_context` uses the HTTP API storage convention
  (board=feature_name, scope="feature"|"project"|"global") to match messages
  posted via `/comms/post`. This is inverse of SPEC §6.1 schema comments but
  matches the actual Conv-2 implementation in blueprints/comms.py.
- Path normalization: project_root is normalized to forward-slash format before
  use as a board query key, matching how HTTP clients supply it.
