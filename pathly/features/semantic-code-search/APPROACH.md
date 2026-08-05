# Semantic Code Search — Approach

## The gap this closes

Pathly's `/code/query` gateway today offers two engines — `graph` (codebase-memory-mcp:
symbols/callers/impact/chain) and `lsp` (Serena: precise, always-fresh single-symbol). Both are
**structural**: they answer *"who calls X / what breaks / where is X defined."* Neither answers
the **semantic** question — *"find the code that does X"* / *"where is auth handled?"* — when the
agent doesn't already know the symbol name. That is the one code-intelligence capability the
market has (Sourcegraph, Cody, CocoIndex-style embedding search) that Pathly measurably lacks
(confirmed in the industry gap analysis). This plan adds it as a **third engine** behind the
existing gateway.

```
  /code/query  engine=…
    ├─ graph     → CliProvider   (codebase-memory-mcp)   structural, breadth   [HAVE]
    ├─ lsp       → LspProvider   (Serena)                 structural, fresh     [HAVE]
    ├─ both      → CompositeProvider(graph, lsp)                                [HAVE]
    └─ semantic  → SemanticProvider (embeddings)          MEANING-based search  [THIS PLAN]
```

## Why it fits cleanly (reuse, don't reinvent)

Every piece needed already exists on a stable seam — this is an *additive* provider, not new
infrastructure:

| Reused piece | Where | Role here |
|---|---|---|
| `CodeContextProvider` protocol + `get_provider()` | `runner/code_context.py` | add one `"semantic"` branch |
| `_ENGINE_TO_BACKEND` map | `http_server/blueprints/code/query.py` | add `"semantic": "semantic"` |
| Local embedding model (`embed()`/`warm()`, bounded LRU, retry, `embedder_status`) | `runner/embeddings.py` | embed code chunks + the query — **no new model, no egress** |
| sqlite-vec (vec0) pattern + `store_chunk_embeddings`/`search_by_embedding` | `comms_embeddings` / `comms_chunk_embeddings` | mirror for a new `code_embeddings` table |
| Debounced fire-and-forget reindex | `code_context.maybe_reindex` | mirror for the code-embedding index |
| never-raise / safe-null contract | `code_context.build_block`, `/code/query` | inherited verbatim |
| role/op gating, content-hash cache, board logging | `/code/query` `_gate`/`_QUERY_CACHE`/`_log_query` | add the `search` op to the tier map |

The whole point: Pathly already embeds *board artifacts*; this plan embeds *code files* with the
same machinery.

## Architecture

- **`runner/code_context_semantic.py` (NEW)** — `SemanticProvider` implementing the
  `CodeContextProvider` protocol. For the `search` op it treats `target` as a **natural-language
  query** (not a path/symbol), embeds it via `embeddings.embed()`, runs a vec0 KNN over
  `code_embeddings`, and returns a ranked `## Code matches` block (`path:line` + the chunk snippet
  + score). Never raises → `""` on any failure (empty index, model unavailable) so the agent
  degrades to Grep.
- **`code_embeddings` table (NEW migration)** — one row per code chunk:
  `{id, project_root, path, chunk_start, chunk_end, content_hash, embedding}` in a vec0 virtual
  table, mirroring `comms_chunk_embeddings`. Keyed for incremental rebuild by `(path, content_hash)`.
- **The indexer (NEW, in `code_context_semantic.py` or a small `code_index.py`)** — walks the
  repo (respecting `.gitignore`), chunks each source file, embeds each chunk, upserts rows.
  **Chunking v1 = fixed line-window with overlap** (simple, language-agnostic); **v2 = function/
  class chunks** (reuse codebase-memory-mcp's existing tree-sitter parse rather than re-parsing).
  Incremental: skip files whose `content_hash` is unchanged (same idea as the graph's
  `maybe_reindex` and the artifact section indexer's `indexed_hash`).
- **Gateway wiring** — `query.py`: add `"semantic"` to `_ENGINE_TO_BACKEND`, and add a `search`
  op to `_TIER_OPS` (e.g. `full` + `lookup` tiers may `search`; keep it broad — discovery is
  low-risk). `get_provider("semantic")` returns `SemanticProvider`. `both` stays graph+lsp;
  a later `all` composite could add semantic.
- **Freshness** — a debounced background reindex (`maybe_reindex_semantic`) fired from the same
  seams as the graph: per stage in runner prompt assembly + on-demand from `/code/query`. v1
  reindexes changed files only; a file-watch upgrade is deferred.

## Config

Selectable per-request via `engine=semantic` (no setting needed to *try* it). A persisted
opt-in mirrors the existing pattern: `code_context.semantic = off | on` (default `off` until an
index exists) so it can join `auto`/`both` composites later without surprising existing installs.
Local-only — reuses the bundled MiniLM model; **no network, no API keys.**

## What it touches (backend only)

| What | File | New/Edit |
|---|---|---|
| Semantic provider + query-side search | `runner/code_context_semantic.py` | **New** |
| `code_embeddings` vec0 table | `db/migrations.py` (+ a `db/queries/code_embeddings.py`) | **New** |
| Register the engine | `runner/code_context.py` (`get_provider`) | Edit (one branch) |
| Route the engine + gate the `search` op | `http_server/blueprints/code/query.py` | Edit (`_ENGINE_TO_BACKEND`, `_TIER_OPS`) |
| Incremental reindex seam | `runner/code_context.py` (mirror `maybe_reindex`) | Edit |
| Tests | `tests/code_intel/` | **New** |

No FSM, no supervisor, no Studio required for v1 (a Studio engine-picker option is a trivial
follow-on). Honors the layer rule (`runner` imports `db`; `http_server` imports `runner` lazily
in the handler).

## Stories (see USER_STORIES.md)

1. `code_embeddings` table + `SemanticProvider` skeleton (safe-off; `""` on empty index).
2. The indexer — chunk + embed + upsert, incremental by content-hash.
3. Wire `engine=semantic` + the `search` op into the gateway (role-gated, cached, board-logged).
4. Incremental reindex seam (debounced, fire-and-forget, never blocks).
5. End-to-end: `/code/query {op:"search", engine:"semantic", target:"<NL query>"}` returns ranked
   `path:line` matches on this repo; graceful Grep fallback when the index is empty/absent.

## Rollout order

1. Table + provider skeleton (safe-off end-to-end).
2. Indexer (line-window v1), incremental.
3. Gateway engine + op wiring.
4. Reindex seam.
5. Smoke test + tune (chunk size, KNN `k`, score floor). Later: function-level chunks (v2),
   Studio picker option, an `all` composite (graph + lsp + semantic).

## Open questions

- **Chunk granularity** — line-window (v1, simple) vs function/class via codebase-memory-mcp's
  existing parse (v2, better recall). Start v1; the table shape supports both.
- **Index scope/size** — whole repo vs a source-dir allowlist; cap total chunks with a documented
  drop (never silently truncate).
- **`search` result shape** — snippets inline (token cost) vs `path:line` pointers + a hydrate
  step (mirror the context-retrieval two-tier "pointer, not payload" model). Default: pointers +
  short snippet.
- **Relevance floor** — a cosine ceiling like `comms_embeddings.SEMANTIC_DISTANCE_CEILING` so weak
  matches return `[]` rather than noise.
