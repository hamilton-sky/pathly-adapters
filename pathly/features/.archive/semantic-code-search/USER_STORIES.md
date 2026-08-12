# User Stories — semantic-code-search

Adds a third `/code/query` engine — `semantic` — for meaning-based code search ("find the code
that does X"), the one code-intelligence axis Pathly's graph + lsp engines don't cover. Reuses the
existing local embedding stack (`runner/embeddings.py` + sqlite-vec). See `APPROACH.md`.

---

## Story 1 — `code_embeddings` table + `SemanticProvider` skeleton (safe-off)

**Who:** Maintainer wiring the new engine.
**What:** A `code_embeddings` vec0 table and a `SemanticProvider` implementing `CodeContextProvider`
that returns `""` when the index is empty or the embedder is unavailable.
**Why:** Ship safe-off — the engine exists and never breaks a prompt before the index is built.

**Acceptance criteria:**
- `db/migrations.py` creates `code_embeddings` (`id, project_root, path, chunk_start, chunk_end,
  content_hash, embedding`) mirroring the `comms_chunk_embeddings` vec0 pattern; idempotent.
- `runner/code_context_semantic.py` defines `SemanticProvider` with `name = "semantic"` and
  `build_block(...)` that **never raises** and returns `""` on empty index / unavailable embedder.
- `runner/code_context.py::get_provider("semantic")` returns `SemanticProvider`.
- Module imports only `db` (layer rule); no supervisor/http_server imports.

---

## Story 2 — Incremental code indexer

**Who:** Developer whose repo should become searchable.
**What:** An indexer walks the repo (respecting `.gitignore`), chunks source files, embeds each
chunk via `embeddings.embed()`, and upserts `code_embeddings` rows — skipping files whose
`content_hash` is unchanged.
**Why:** Builds the searchable index cheaply and keeps it current without full rebuilds.

**Acceptance criteria:**
- Chunking v1 = fixed line-window with overlap; deterministic `chunk_start`/`chunk_end`.
- Re-running the indexer on an unchanged repo re-embeds nothing (all `content_hash` match).
- Editing one file re-embeds only that file's chunks.
- A total-chunk cap is enforced and the drop is `log()`-ged (no silent truncation).
- Never raises — an unreadable/binary file is skipped, not fatal.

---

## Story 3 — Wire `engine=semantic` + the `search` op into the gateway

**Who:** Any agent calling `/code/query`.
**What:** `POST /code/query {op:"search", engine:"semantic", target:"<NL query>"}` embeds the
query, KNN-searches `code_embeddings`, and returns a ranked `## Code matches` block of
`path:line` + snippet; role-gated, content-hash cached, board-logged like the other ops.
**Why:** Exposes semantic search through the one gateway agents already use — no new transport.

**Acceptance criteria:**
- `query.py` `_ENGINE_TO_BACKEND` maps `"semantic" → "semantic"`.
- `search` is added to `_TIER_OPS` for the appropriate tiers (at least `full` + `lookup`).
- A permitted role's `search` returns ranked matches; an excluded role gets the existing
  safe-null `reason:"disabled"`; an out-of-tier op gets `"op-not-permitted"`.
- Weak matches are floored by a cosine ceiling (mirror `SEMANTIC_DISTANCE_CEILING`) → `[]`/null,
  not noise.
- Empty index → safe-null (`result:null`), never a 500; agent falls back to Grep.

---

## Story 4 — Incremental reindex seam (debounced, non-blocking)

**Who:** Agents running across pipeline stages.
**What:** A `maybe_reindex_semantic(project_root)` fired from the same seams as the graph
(per-stage prompt assembly + on-demand from `/code/query`), debounced and fire-and-forget.
**Why:** Keeps the semantic index reasonably fresh between edits without blocking any request.

**Acceptance criteria:**
- Reindex runs in a daemon thread, never blocks the response, and is debounced (≤ once per window,
  mirroring `_REINDEX_DEBOUNCE_S`).
- No-op when `code_context.semantic` is off or the embedder is unavailable.
- Never raises.

---

## Story 5 — End-to-end semantic search + graceful fallback

**Who:** Developer/agent searching this repo.
**What:** After indexing, a natural-language `search` query returns relevant `path:line` matches;
with the index empty/disabled the same call degrades cleanly to Grep.
**Why:** Proves the engine end-to-end and the safe-fallback contract.

**Acceptance criteria:**
- With the index built, `{op:"search", engine:"semantic", target:"where is code intelligence
  routed"}` returns results pointing at the real `code_context`/`code/query` files.
- With `code_context.semantic=off` (or no index), the same call returns safe-null and the agent
  proceeds via Grep — no crash, no missing-tool error.
- A `tests/code_intel/` suite covers: empty-index safe-null, indexer incrementality, role gating
  for `search`, and a ranked-result assertion.
