---
name: Progress
---
# Comms Board (Phase 1 — Backend Core) — Progress

## Status: COMPLETE (all phases done · reviewed · 469 passed / 6 pre-existing failures)

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

## Conversation Breakdown

| Conv | Phases | Stories | Status | Verify |
|------|--------|---------|--------|--------|
| 1 | 1–5 | S1.1, S1.2 | DONE | `python -m pytest tests/ -q -k comms` |
| 2 | 6–8 | S1.3, S1.4 | DONE | `curl POST /comms/post` then `GET /comms` round-trips |
| 3 | 9–10 | S2.1, S2.2 | DONE | `/next_action` output contains `## Communication Board` |

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

## Prerequisites
- Python 3.10+, package installed editable (`pip install -e .`)
- `~/.pathly/pathly.db` writable
- SQLite built with `enable_load_extension` (else recency fallback is exercised)

## Blocked By
- Nothing

## Conv 3 Notes
- Phase 10 implemented first (board_scope storage in app_settings).
- Phase 9 `retrieve_board_context` uses the HTTP API storage convention
  (board=feature_name, scope="feature"|"project"|"global") to match messages
  posted via `/comms/post`. This is inverse of SPEC §6.1 schema comments but
  matches the actual Conv-2 implementation in blueprints/comms.py.
- Path normalization: project_root is normalized to forward-slash format before
  use as a board query key, matching how HTTP clients supply it.
